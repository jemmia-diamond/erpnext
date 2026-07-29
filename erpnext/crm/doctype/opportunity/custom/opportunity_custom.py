import frappe
from frappe.query_builder import DocType, Interval
from frappe.query_builder.functions import Now
from erpnext.utilities.phone_utils import get_phone_variants


def auto_close_opportunity():
	"""Auto set Opportunity to Lost according to spec in docs (Line 83):
	1. Past expected_delivery_date + 7 days without interaction -> Lost.
	2. 7 days inactive in Nurturing status without interaction -> Lost.
	"""
	enabled = frappe.db.get_single_value("CRM Settings", "auto_close_opportunity")
	if not enabled:
		return

	auto_close_after_days = frappe.db.get_single_value("CRM Settings", "close_opportunity_after_days") or 7
	cutoff = frappe.utils.add_days(frappe.utils.now_datetime(), -auto_close_after_days)
	today_date = frappe.utils.nowdate()

	opps = frappe.get_all(
		"Opportunity",
		filters={
			"status": ["in", ["Nurturing", "Open", "Negotiation", "Delayed"]],
		},
		fields=["name", "status", "expected_delivery_date", "last_customer_message_at", "last_sales_message_at", "modified"],
	)

	target_opps = []
	for opp in opps:
		cust_at = opp.last_customer_message_at
		sales_at = opp.last_sales_message_at

		# Rule B (Doc Line 83): Past expected purchase date + 7 days without interaction -> Lost
		if opp.expected_delivery_date:
			exp_cutoff = frappe.utils.add_days(opp.expected_delivery_date, 7)
			if str(today_date) > str(exp_cutoff):
				if (not cust_at or frappe.utils.get_datetime(cust_at) < cutoff) and (
					not sales_at or frappe.utils.get_datetime(sales_at) < cutoff
				):
					target_opps.append((opp.name, f"Tự động đóng: Quá 7 ngày tính từ ngày mua dự kiến ({opp.expected_delivery_date})"))
					continue

		# Rule A (Doc Line 83): Inactive for over 7 days in Nurturing status without interaction -> Lost
		if opp.status == "Nurturing":
			if (not cust_at or frappe.utils.get_datetime(cust_at) < cutoff) and (
				not sales_at or frappe.utils.get_datetime(sales_at) < cutoff
			) and (frappe.utils.get_datetime(opp.modified) < cutoff):
				target_opps.append((opp.name, "Tự động đóng: Quá 7 ngày ở Nuôi dưỡng mà không có tương tác"))

	if target_opps:
		if not frappe.db.exists("Opportunity Lost Reason", "Auto Lost"):
			frappe.get_doc({"doctype": "Opportunity Lost Reason", "lost_reason": "Auto Lost"}).insert(
				ignore_permissions=True, ignore_if_duplicate=True
			)

		for opp_name, reason_text in target_opps:
			opp = frappe.get_doc("Opportunity", opp_name)
			opp.status = "Lost"
			opp.order_lost_reason = reason_text
			if not any(r.lost_reason == "Auto Lost" for r in opp.lost_reasons):
				opp.append("lost_reasons", {"lost_reason": "Auto Lost"})
			opp.flags.ignore_permissions = True
			opp.flags.ignore_mandatory = True
			opp.save()


def mark_opportunity_as_won_on_payment(doc, method=None):
	"""Auto-win active Opportunities linked to Customer, Customer's original Lead, or Phone variants."""
	customer_name = doc.party or getattr(doc, "party_name", None)
	if not customer_name:
		return

	# Collect linked parties (Customer name + Lead name if Customer came from Lead)
	parties = {customer_name}
	cust_lead, phone1, phone2 = frappe.db.get_value(
		"Customer", customer_name, ["lead_name", "phone", "mobile_no"]
	) or (None, None, None)

	if cust_lead:
		parties.add(cust_lead)

	# Collect all phone variants
	raw_phones = {p for p in (phone1, phone2, getattr(doc, "contact_mobile", None)) if p}
	variants = {v for p in raw_phones for v in get_phone_variants(p)}

	# Single query to find matching active opportunities
	or_filters = [["party_name", "in", list(parties)]]
	if variants:
		or_filters.append(["phone", "in", list(variants)])

	opp_names = frappe.get_all(
		"Opportunity",
		filters=[["status", "not in", ["Won", "Lost"]]],
		or_filters=or_filters,
		pluck="name"
	)

	if opp_names:
		frappe.db.set_value("Opportunity", opp_names, "status", "Won")
