import frappe
from frappe import _
from erpnext.utilities.phone_utils import get_phone_variants


@frappe.whitelist()
def update_party(appointment=None, appointment_name=None, to_type=None):
	"""
	Whitelisted API to switch an Appointment's party between Lead and Customer.
	Accepts appointment name from client/UI.

	1. If switching to Customer (current appointment_with == 'Lead'):
	   - Primary: Looks up Customer from mapped `sales_order.customer`.
	   - Fallback: Finds Customer by `Customer.lead_name == appointment.party` (or appointment.lead).
	   - Fallback 2: Searches Customer by customer_phone_number variants.
	   - Sets appointment.appointment_with = "Customer", appointment.party = customer.

	2. If switching to Lead (current appointment_with == 'Customer'):
	   - Primary: Looks up Lead from `customer.lead_name`.
	   - Fallback: Uses `appointment.lead` if already populated.
	   - Fallback 2: Searches Lead by customer_phone_number variants.
	   - Sets appointment.appointment_with = "Lead", appointment.party = lead, appointment.lead = lead.
	"""
	name = (
		appointment
		or appointment_name
		or frappe.form_dict.get("appointment")
		or frappe.form_dict.get("appointment_name")
		or frappe.form_dict.get("name")
	)

	if not name:
		frappe.throw(_("Appointment name is required."))

	appt = frappe.get_doc("Appointment", name)

	if not to_type:
		target_type = "Customer" if appt.appointment_with == "Lead" else "Lead"
	else:
		target_type = to_type

	if target_type == "Customer":
		customer = None

		# 1. From mapped sales order
		if appt.sales_order:
			customer = frappe.db.get_value("Sales Order", appt.sales_order, "customer")

		# 2. From Customer where lead_name == current party or lead
		if not customer and appt.party:
			customer = frappe.db.get_value("Customer", {"lead_name": appt.party}, "name", order_by="creation desc")
		if not customer and appt.lead:
			customer = frappe.db.get_value("Customer", {"lead_name": appt.lead}, "name", order_by="creation desc")

		# 3. Fallback: Search by phone variants
		if not customer and appt.customer_phone_number:
			variants = get_phone_variants(appt.customer_phone_number)
			customer = frappe.db.get_value("Customer", {"mobile_no": ("in", variants)}, "name")
			if not customer:
				customer = frappe.db.get_value("Customer", {"phone": ("in", variants)}, "name")

		if not customer:
			frappe.throw(
				_("No Customer found for Appointment {0} (Lead: {1}).").format(
					appt.name, appt.party or appt.lead or "N/A"
				)
			)

		appt.appointment_with = "Customer"
		appt.party = customer

		cust_name = frappe.db.get_value("Customer", customer, "customer_name")
		if cust_name:
			appt.customer_name = cust_name

		appt.save(ignore_permissions=True)

		return {
			"status": "success",
			"appointment": appt.name,
			"appointment_with": appt.appointment_with,
			"party": appt.party,
			"customer_name": appt.customer_name,
		}

	elif target_type == "Lead":
		lead = None

		# 1. From Customer.lead_name
		if appt.party and appt.appointment_with == "Customer":
			lead = frappe.db.get_value("Customer", appt.party, "lead_name")

		# 2. From appt.lead
		if not lead and appt.lead and frappe.db.exists("Lead", appt.lead):
			lead = appt.lead

		# 3. Fallback: Search by phone variants
		if not lead and appt.customer_phone_number:
			variants = get_phone_variants(appt.customer_phone_number)
			lead = frappe.db.get_value("Lead", {"mobile_no": ("in", variants)}, "name")
			if not lead:
				lead = frappe.db.get_value("Lead", {"phone": ("in", variants)}, "name")

		if not lead:
			frappe.throw(
				_("No Lead found for Appointment {0} (Customer: {1}).").format(
					appt.name, appt.party or "N/A"
				)
			)

		appt.appointment_with = "Lead"
		appt.party = lead
		appt.lead = lead

		lead_name = frappe.db.get_value("Lead", lead, "lead_name")
		if lead_name:
			appt.customer_name = lead_name

		appt.save(ignore_permissions=True)

		return {
			"status": "success",
			"appointment": appt.name,
			"appointment_with": appt.appointment_with,
			"party": appt.party,
			"customer_name": appt.customer_name,
		}

	else:
		frappe.throw(_("Invalid target type {0}. Must be 'Lead' or 'Customer'.").format(target_type))


@frappe.whitelist()
def switch_to_customer(appointment=None, appointment_name=None):
	"""Explicit endpoint to switch an Appointment to Customer."""
	return update_party(appointment=appointment, appointment_name=appointment_name, to_type="Customer")


@frappe.whitelist()
def switch_to_lead(appointment=None, appointment_name=None):
	"""Explicit endpoint to switch an Appointment to Lead."""
	return update_party(appointment=appointment, appointment_name=appointment_name, to_type="Lead")
