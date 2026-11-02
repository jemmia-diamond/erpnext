import frappe
from frappe.utils import add_to_date, getdate, now_datetime
from erpnext.utilities.phone_utils import get_phone_variants


def get_sales_order_group_info(so_name, split_order_group_name=None, grand_total=0.0, group_cache=None):
	"""
	Returns (total_group_amount, group_order_names) for a given sales order.
	If in a split group:
	  Calculates sum of uncancelled orders and lists their names sorted by creation.
	Otherwise:
	  Returns the single order's grand_total and name.
	"""
	if group_cache is None:
		group_cache = {}

	if split_order_group_name:
		if split_order_group_name not in group_cache:
			orders = frappe.db.sql(
				"""
				SELECT name, grand_total
				FROM `tabSales Order`
				WHERE split_order_group_name = %s
				  AND cancelled_status = 'Uncancelled'
				ORDER BY creation ASC
				""",
				(split_order_group_name,),
				as_dict=True,
			)
			if orders:
				total = sum(float(row.grand_total or 0) for row in orders)
				names = ", ".join(row.name for row in orders)
				group_cache[split_order_group_name] = (total, names)
			else:
				group_cache[split_order_group_name] = (float(grand_total or 0), so_name or "")

		return group_cache[split_order_group_name]

	return float(grand_total or 0), (so_name or "")


def cleanup_duplicate_appointment_sales_orders():
	"""
	Cleans up existing appointments sharing the same Sales Order.
	Keeps the appointment closest to the Sales Order real_order_date (appt_date <= order_date),
	and unmaps older duplicate appointments (sets sales_order=None, group_order_grand_total=0.0, sales_order_group_names=None).
	Also unmaps any appointment where real_order_date is strictly before the appointment's scheduled date.
	"""
	duplicates = frappe.db.sql(
		"""
		SELECT sales_order, COUNT(*) AS cnt
		FROM `tabAppointment`
		WHERE sales_order IS NOT NULL AND sales_order != ''
		GROUP BY sales_order
		HAVING cnt > 1
		""",
		as_dict=True,
	)

	unmapped_appointments = []
	for dup in duplicates:
		so_name = dup["sales_order"]
		so = frappe.db.get_value(
			"Sales Order", so_name, ["creation", "real_order_date", "transaction_date"], as_dict=True
		)
		if not so:
			continue
		order_date = so.real_order_date or so.transaction_date or getdate(so.creation)

		appts = frappe.db.sql(
			"""
			SELECT name, scheduled_time
			FROM `tabAppointment`
			WHERE sales_order = %s
			ORDER BY scheduled_time DESC
			""",
			(so_name,),
			as_dict=True,
		)

		valid_appts = [a for a in appts if getdate(a.scheduled_time) <= order_date]
		keep_appt = valid_appts[0] if valid_appts else appts[0]

		for appt in appts:
			if appt.name != keep_appt.name:
				frappe.db.set_value(
					"Appointment",
					appt.name,
					{
						"sales_order": None,
						"group_order_grand_total": 0.0,
						"sales_order_group_names": None,
					},
					update_modified=False,
				)
				unmapped_appointments.append({"appointment": appt.name, "sales_order": so_name, "kept": keep_appt.name})

	# Unmap any appointment whose sales order real_order_date is strictly before scheduled date
	mismatched = frappe.db.sql(
		"""
		SELECT appt.name, appt.sales_order
		FROM `tabAppointment` appt
		JOIN `tabSales Order` so ON so.name = appt.sales_order
		WHERE appt.sales_order IS NOT NULL AND appt.sales_order != ''
		  AND so.real_order_date IS NOT NULL
		  AND so.real_order_date < DATE(appt.scheduled_time)
		""",
		as_dict=True,
	)
	for row in mismatched:
		frappe.db.set_value(
			"Appointment",
			row.name,
			{
				"sales_order": None,
				"group_order_grand_total": 0.0,
				"sales_order_group_names": None,
			},
			update_modified=False,
		)
		unmapped_appointments.append({
			"appointment": row.name,
			"sales_order": row.sales_order,
			"kept": None,
			"reason": "real_order_date before scheduled_time",
		})

	if unmapped_appointments:
		frappe.db.commit()

	return unmapped_appointments


def map_sales_orders_to_appointments():
	"""
	Hourly cron job:
	1. Cleans up any existing duplicate appointment mappings (keeps only the closest appointment to SO real_order_date).
	2. Maps recently created Sales Orders to Appointments based on:
	   - Order date is based on real_order_date (Date), falling back to transaction_date / creation date.
	   - Appointment scheduled date <= Sales Order real_order_date
	   - Appointment scheduled date within 15 days of Sales Order real_order_date
	   - 1 Sales Order maps to at most 1 Appointment (the closest scheduled_time on or before real_order_date).
	   - Split orders in the same group do not greedily map to older appointments.
	   - Sales Order cancelled_status == 'Uncancelled' (no docstatus check)
	   - Both SO and Appointment within recent 15-day window (now() - 15 days)
	   - Appointment customer_phone_number matches any phone variant of Sales Order's customer
	   - Sets sales_order, group_order_grand_total, and sales_order_group_names
	3. Syncs group_order_grand_total and sales_order_group_names for mapped appointments in 15-day window
	"""
	# Rule 3: Clean up duplicate / mismatched mappings first
	cleanup_duplicate_appointment_sales_orders()

	earliest_time = add_to_date(now_datetime(), days=-15)
	earliest_date = add_to_date(now_datetime(), days=-15).date()
	group_cache = {}

	# Track Sales Orders already mapped to an appointment
	mapped_so_names = set(
		frappe.db.sql_list(
			"""
			SELECT DISTINCT sales_order
			FROM `tabAppointment`
			WHERE sales_order IS NOT NULL AND sales_order != ''
			"""
		)
	)

	# Track split order groups already mapped to an appointment (Rule 2: avoid sibling orders claiming older appointments)
	mapped_split_groups = set(
		frappe.db.sql_list(
			"""
			SELECT DISTINCT so.split_order_group_name
			FROM `tabAppointment` appt
			JOIN `tabSales Order` so ON so.name = appt.sales_order
			WHERE appt.sales_order IS NOT NULL AND appt.sales_order != ''
			  AND so.split_order_group_name IS NOT NULL AND so.split_order_group_name != ''
			"""
		)
	)

	# Fetch uncancelled Sales Orders within last 15 days (by creation or real_order_date)
	sales_orders = frappe.db.sql(
		"""
		SELECT
			so.name,
			so.customer,
			so.creation,
			so.real_order_date,
			so.transaction_date,
			COALESCE(so.real_order_date, so.transaction_date, DATE(so.creation)) AS order_date,
			so.contact_phone,
			so.contact_mobile,
			so.grand_total,
			so.split_order_group_name,
			c.mobile_no AS cust_mobile_no,
			c.phone AS cust_phone
		FROM `tabSales Order` so
		LEFT JOIN `tabCustomer` c ON c.name = so.customer
		WHERE so.cancelled_status = 'Uncancelled'
		  AND so.grand_total > 1000
		  AND (so.source_name IS NULL OR so.source_name NOT IN ('bhsc-cua-hang-hcm', 'bhsc-cua-hang-hn'))
		  AND (so.creation >= %(earliest_time)s OR COALESCE(so.real_order_date, so.transaction_date) >= %(earliest_date)s)
		ORDER BY COALESCE(so.real_order_date, so.transaction_date, DATE(so.creation)) DESC, so.creation DESC
		""",
		{"earliest_time": earliest_time, "earliest_date": earliest_date},
		as_dict=True,
	)

	# Fetch candidate unmapped appointments scheduled within last 15 days
	unmapped_appointments = frappe.db.sql(
		"""
		SELECT
			name,
			customer_phone_number,
			scheduled_time
		FROM `tabAppointment`
		WHERE (sales_order IS NULL OR sales_order = '')
		  AND customer_phone_number IS NOT NULL
		  AND customer_phone_number != ''
		  AND scheduled_time >= %(earliest_time)s
		ORDER BY scheduled_time DESC
		""",
		{"earliest_time": earliest_time},
		as_dict=True,
	)

	if sales_orders and unmapped_appointments:
		for so in sales_orders:
			# Skip if this Sales Order is already mapped to an appointment
			if so.name in mapped_so_names:
				continue

			# Rule 2: Skip if this split group is already mapped to an appointment
			if so.split_order_group_name and so.split_order_group_name in mapped_split_groups:
				continue

			order_date = getdate(so.order_date)
			cutoff_date = add_to_date(order_date, days=-15)

			# Collect phone numbers for this Sales Order / Customer
			phones = set()
			for p in [so.contact_mobile, so.contact_phone, so.cust_mobile_no, so.cust_phone]:
				if p:
					phones.add(str(p).strip())

			if not phones:
				continue

			# Expand all phone variants
			variants = set()
			for p in phones:
				for v in get_phone_variants(p):
					if v:
						variants.add(str(v).strip())

			if not variants:
				continue

			# Rule 1: Find closest matching appointment (unmapped_appointments is ORDER BY scheduled_time DESC)
			# Order date must be on or after appointment scheduled date, within 15 days
			target_appt = None
			for appt in unmapped_appointments:
				appt_phone = str(appt.customer_phone_number).strip()
				if appt_phone in variants:
					appt_date = getdate(appt.scheduled_time)
					if cutoff_date <= appt_date <= order_date:
						target_appt = appt
						break

			if target_appt:
				try:
					group_total, group_names = get_sales_order_group_info(
						so.name, so.split_order_group_name, so.grand_total, group_cache
					)
					frappe.db.set_value(
						"Appointment",
						target_appt.name,
						{
							"sales_order": so.name,
							"group_order_grand_total": group_total,
							"sales_order_group_names": group_names,
						},
						update_modified=False,
					)
					unmapped_appointments.remove(target_appt)
					mapped_so_names.add(so.name)
					if so.split_order_group_name:
						mapped_split_groups.add(so.split_order_group_name)
				except Exception as e:
					frappe.log_error(f"Failed to map Sales Order {so.name} to Appointment {target_appt.name}: {e!s}")

	# Sync group totals and group names for existing mapped appointments in the 15-day window
	mapped_appointments = frappe.db.sql(
		"""
		SELECT
			appt.name,
			appt.sales_order,
			appt.group_order_grand_total,
			appt.sales_order_group_names,
			so.grand_total,
			so.split_order_group_name,
			so.cancelled_status
		FROM `tabAppointment` appt
		JOIN `tabSales Order` so ON so.name = appt.sales_order
		WHERE appt.sales_order IS NOT NULL
		  AND appt.sales_order != ''
		  AND appt.scheduled_time >= %(earliest_time)s
		""",
		{"earliest_time": earliest_time},
		as_dict=True,
	)

	for appt in mapped_appointments:
		try:
			if appt.cancelled_status == "Cancelled" and not appt.split_order_group_name:
				expected_total, expected_names = 0.0, appt.sales_order
			else:
				expected_total, expected_names = get_sales_order_group_info(
					appt.sales_order, appt.split_order_group_name, appt.grand_total, group_cache
				)

			updates = {}
			if float(appt.group_order_grand_total or 0) != float(expected_total):
				updates["group_order_grand_total"] = expected_total
			if (appt.sales_order_group_names or "") != (expected_names or ""):
				updates["sales_order_group_names"] = expected_names

			if updates:
				frappe.db.set_value("Appointment", appt.name, updates, update_modified=False)
		except Exception as e:
			frappe.log_error(f"Failed to sync group order fields for Appointment {appt.name}: {e!s}")

	frappe.db.commit()
