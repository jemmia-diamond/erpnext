import frappe
from frappe.utils import flt, get_first_day, today
from erpnext.accounts.doctype.payment_entry.services.cron import find_active_replacement
from erpnext.crm.doctype.appointment.services.cron import get_sales_order_group_info


@frappe.whitelist()
def update_cancelled_sales_orders_in_appointments(since=None, appointments=None):
	"""
	Hourly cron job, also callable manually:
	Scans Appointments linked to a cancelled Sales Order (within this month)
	and remaps them to the active uncancelled Sales Order that replaced it.

	1. Finds Appointments where sales_order has cancelled_status == 'Cancelled'
	   within the time range (defaults to the beginning of the current month).
	2. Resolves active replacement via find_active_replacement() (walking chains).
	3. Re-calculates group_order_grand_total and sales_order_group_names.
	4. Updates the Appointment record (update_modified=False).
	"""
	if appointments:
		if isinstance(appointments, str):
			appointments = frappe.parse_json(appointments) if appointments.startswith("[") else [appointments]
		date_filter = "AND appt.name IN %(appointments)s"
		values = {"appointments": tuple(appointments)}
	else:
		if not since:
			since = get_first_day(today())
		date_filter = "AND (appt.scheduled_time >= %(since)s OR appt.creation >= %(since)s OR so.modified >= %(since)s)"
		values = {"since": since}

	stale_appointments = frappe.db.sql(
		f"""
		SELECT
			appt.name AS appointment,
			appt.sales_order AS old_sales_order,
			appt.group_order_grand_total,
			appt.sales_order_group_names,
			so.name AS so_name,
			so.order_number,
			so.cancelled_status,
			so.split_order_group_name
		FROM `tabAppointment` appt
		INNER JOIN `tabSales Order` so ON so.name = appt.sales_order
		WHERE appt.sales_order IS NOT NULL
		  AND appt.sales_order != ''
		  AND so.cancelled_status = 'Cancelled'
		  {date_filter}
		ORDER BY appt.modified DESC
		""",
		values,
		as_dict=True,
	)

	result = {"remapped": [], "no_replacement": [], "failed": []}
	target_cache = {}
	group_cache = {}

	for row in stale_appointments:
		old_so = row.old_sales_order
		if old_so not in target_cache:
			target_cache[old_so] = find_active_replacement(old_so)

		target_so_name = target_cache[old_so]

		if not target_so_name:
			# If no replacement was found, re-evaluate group total (may drop to remaining uncancelled orders or 0)
			group_total, group_names = get_sales_order_group_info(
				row.old_sales_order, row.split_order_group_name, 0.0, group_cache
			)
			if flt(row.group_order_grand_total) != group_total or (row.sales_order_group_names or "") != group_names:
				frappe.db.set_value(
					"Appointment",
					row.appointment,
					{
						"group_order_grand_total": group_total,
						"sales_order_group_names": group_names,
					},
					update_modified=False,
				)
			result["no_replacement"].append({"appointment": row.appointment, "from": old_so})
			continue

		try:
			target_so = frappe.db.get_value(
				"Sales Order",
				target_so_name,
				["name", "split_order_group_name", "grand_total", "order_number"],
				as_dict=True,
			)
			if not target_so:
				result["failed"].append({"appointment": row.appointment, "from": old_so, "to": target_so_name, "error": "Target SO not found"})
				continue

			group_total, group_names = get_sales_order_group_info(
				target_so.name, target_so.split_order_group_name, target_so.grand_total, group_cache
			)

			frappe.db.set_value(
				"Appointment",
				row.appointment,
				{
					"sales_order": target_so.name,
					"group_order_grand_total": group_total,
					"sales_order_group_names": group_names,
				},
				update_modified=False,
			)
			result["remapped"].append({
				"appointment": row.appointment,
				"from": old_so,
				"to": target_so.name,
				"to_order_number": target_so.order_number,
				"group_total": group_total,
				"group_names": group_names,
			})
		except Exception as e:
			frappe.log_error(
				f"Failed to remap Appointment {row.appointment} from {old_so} to {target_so_name}: {e!s}",
				"Appointment Cancelled SO Remap Error",
			)
			result["failed"].append({
				"appointment": row.appointment,
				"from": old_so,
				"to": target_so_name,
				"error": str(e),
			})

	frappe.db.commit()
	return result
