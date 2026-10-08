import frappe
from frappe.utils import add_to_date, now_datetime
from erpnext.utilities.phone_utils import get_phone_variants


def map_sales_orders_to_appointments():
	"""
	Hourly cron job:
	Maps recently created Sales Orders to Appointments based on:
	1. Appointment scheduled_time < Sales Order creation
	2. Appointment scheduled_time within 15 days of Sales Order creation
	3. Sales Order cancelled_status == 'Uncancelled' (no docstatus check)
	4. Both SO and Appointment within recent 15-day window (now() - 15 days)
	5. Appointment customer_phone_number matches any phone variant of Sales Order's customer
	"""
	earliest_time = add_to_date(now_datetime(), days=-15)

	# Fetch uncancelled Sales Orders created within last 15 days
	sales_orders = frappe.db.sql(
		"""
		SELECT
			so.name,
			so.customer,
			so.creation,
			so.contact_phone,
			so.contact_mobile,
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

	if not sales_orders:
		return

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

	if not unmapped_appointments:
		return

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
				frappe.db.set_value("Appointment", appt.name, "sales_order", so.name, update_modified=False)
				unmapped_appointments.remove(appt)
			except Exception as e:
				frappe.log_error(f"Failed to map Sales Order {so.name} to Appointment {appt.name}: {e!s}")

	frappe.db.commit()
