import frappe
from frappe.utils import add_to_date, now_datetime
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


def map_sales_orders_to_appointments():
	"""
	Hourly cron job:
	1. Maps recently created Sales Orders to Appointments based on:
	   - Appointment scheduled_time < Sales Order creation
	   - Appointment scheduled_time within 15 days of Sales Order creation
	   - Sales Order cancelled_status == 'Uncancelled' (no docstatus check)
	   - Both SO and Appointment within recent 15-day window (now() - 15 days)
	   - Appointment customer_phone_number matches any phone variant of Sales Order's customer
	   - Sets sales_order, group_order_grand_total, and sales_order_group_names
	2. Syncs group_order_grand_total and sales_order_group_names for mapped appointments in 15-day window
	"""
	earliest_time = add_to_date(now_datetime(), days=-15)
	group_cache = {}

	# Fetch uncancelled Sales Orders created within last 15 days
	sales_orders = frappe.db.sql(
		"""
		SELECT
			so.name,
			so.customer,
			so.creation,
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
		  AND so.creation >= %(earliest_time)s
		ORDER BY so.creation DESC
		""",
		{"earliest_time": earliest_time},
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
			so_creation = so.creation
			cutoff_time = add_to_date(so_creation, days=-15)

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

			# Find matching appointments
			matched_appts = []
			for appt in unmapped_appointments:
				appt_phone = str(appt.customer_phone_number).strip()
				if appt_phone in variants:
					# Rule: appointment scheduled_time < SO creation AND scheduled_time >= SO creation - 15 days
					if cutoff_time <= appt.scheduled_time < so_creation:
						matched_appts.append(appt)

			for appt in matched_appts:
				try:
					group_total, group_names = get_sales_order_group_info(
						so.name, so.split_order_group_name, so.grand_total, group_cache
					)
					frappe.db.set_value(
						"Appointment",
						appt.name,
						{
							"sales_order": so.name,
							"group_order_grand_total": group_total,
							"sales_order_group_names": group_names,
						},
						update_modified=False,
					)
					unmapped_appointments.remove(appt)
				except Exception as e:
					frappe.log_error(f"Failed to map Sales Order {so.name} to Appointment {appt.name}: {e!s}")

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
