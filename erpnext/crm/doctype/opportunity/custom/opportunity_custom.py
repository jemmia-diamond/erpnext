import json
import time

import frappe
from frappe.query_builder import DocType, Interval
from frappe.query_builder.functions import Now

from erpnext.crm.doctype.crm_settings.crm_settings_service import get_crm_settings
from erpnext.utilities.phone_utils import get_phone_variants

DEFAULT_LEAD_OPPORTUNITY_FIELD_MAPPINGS = [
	("first_name", "title"),
	("phone", "phone"),
	("email_id", "contact_email"),
	("gender", "gender"),
	("age_rage", "age_rage"),
	("purpose_lead", "purpose_lead"),
	("budget_lead", "budget_lead"),
	("province", "province"),
	("region", "region"),
	("preferred_product_type", "preferred_product_type"),
	("expected_delivery_date", "expected_delivery_date"),
	("last_customer_message_at", "last_customer_message_at"),
	("last_sales_message_at", "last_sales_message_at"),
]


def auto_close_opportunity():
	"""Auto set Opportunity to Lost according to spec in docs (Line 83):
	1. Past expected_delivery_date + 7 days without interaction -> Lost.
	2. 7 days inactive in Nurturing status without interaction -> Lost.
	"""
	crm_settings = get_crm_settings()
	enabled = crm_settings.get("auto_close_opportunity", 0)
	if not enabled:
		return

	auto_close_after_days = crm_settings.get("close_opportunity_after_days") or 7
	cutoff_str = frappe.utils.add_days(frappe.utils.now_datetime(), -auto_close_after_days)
	cutoff = frappe.utils.get_datetime(cutoff_str)
	today_date = frappe.utils.nowdate()

	messages = {}
	messages_json = crm_settings.get("lost_reason_messages")
	if messages_json:
		try:
			parsed = frappe.parse_json(messages_json)
			if isinstance(parsed, dict):
				messages = parsed
		except Exception:
			pass

	opps = frappe.get_all(
		"Opportunity",
		filters={
			"status": ["in", ["Nurturing", "Proposal", "Negotiation", "Delayed"]],
		},
		fields=[
			"name",
			"status",
			"expected_delivery_date",
			"last_customer_message_at",
			"last_sales_message_at",
			"modified",
		],
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
					reason = (
						messages.get("auto_lost_opportunity_expected_delivery")
						or f"Tự động đóng: Quá 7 ngày tính từ ngày mua dự kiến ({opp.expected_delivery_date})"
					)
					target_opps.append((opp.name, reason))
					continue

		# Rule A (Doc Line 83): Inactive for over 7 days in Nurturing status without interaction -> Lost
		if opp.status == "Nurturing":
			if (
				(not cust_at or frappe.utils.get_datetime(cust_at) < cutoff)
				and (not sales_at or frappe.utils.get_datetime(sales_at) < cutoff)
				and (frappe.utils.get_datetime(opp.modified) < cutoff)
			):
				reason = (
					messages.get("auto_lost_opportunity_nurturing")
					or "Tự động đóng: Quá 7 ngày ở Nuôi dưỡng mà không có tương tác"
				)
				target_opps.append((opp.name, reason))

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
		"Opportunity", filters=[["status", "not in", ["Won", "Lost"]]], or_filters=or_filters, pluck="name"
	)

	if opp_names:
		frappe.db.set_value("Opportunity", opp_names, "status", "Won")


def sync_lead_fields_to_active_opportunities(doc, method=None):
	"""Sync specified Lead fields to active/in-progress Opportunities (status NOT IN ['Won', 'Lost'])."""
	crm_settings = get_crm_settings()
	enabled = crm_settings.get("sync_lead_to_in_progress_opportunity", 0)
	raw_mappings = crm_settings.get("opportunity_sync_field_mappings")

	if not enabled or not doc or not getattr(doc, "name", None):
		return

	or_filters = [["party_name", "=", doc.name]]
	if doc.get("phone"):
		or_filters.append(["phone", "=", doc.phone])

	opp_names = frappe.get_all(
		"Opportunity",
		filters=[
			["opportunity_from", "in", ["Lead", "Customer"]],
			["status", "not in", ["Won", "Lost"]],
		],
		or_filters=or_filters,
		pluck="name",
	)

	if not opp_names:
		return

	field_mappings = get_lead_to_opportunity_field_mappings(raw_mappings)
	today = frappe.utils.getdate(frappe.utils.nowdate())

	for opp_name in opp_names:
		opp = frappe.get_doc("Opportunity", opp_name)
		updated = False

		for lead_field, opp_field in field_mappings:
			val = doc.get(lead_field)
			if not val:
				continue

			if lead_field == "preferred_product_type":
				lead_items = [r.product_type for r in val if getattr(r, "product_type", None)]
				opp_items = [
					r.product_type for r in opp.preferred_product_type if getattr(r, "product_type", None)
				]
				if lead_items != opp_items:
					opp.set("preferred_product_type", [])
					for pt in lead_items:
						opp.append("preferred_product_type", {"product_type": pt})
					updated = True

			elif lead_field == "expected_delivery_date":
				if not opp.expected_delivery_date:
					doc_exp = frappe.utils.getdate(val)
					if doc_exp >= today:
						opp.expected_delivery_date = val
						updated = True

			else:
				if opp.get(opp_field) != val:
					opp.set(opp_field, val)
					updated = True

		if updated:
			opp.flags.ignore_permissions = True
			opp.flags.ignore_mandatory = True
			opp.flags.ignore_validate = True
			opp.flags.ignore_links = True
			opp.save()


def get_lead_to_opportunity_field_mappings(raw_mappings=None):
	"""Parse custom JSON field mappings from CRM Settings or return default mapping list."""
	if raw_mappings:
		try:
			parsed = frappe.parse_json(raw_mappings)
			if parsed:
				return parsed
		except Exception:
			frappe.log_error(
				title="Invalid Opportunity Sync Field Mappings JSON", message=frappe.get_traceback()
			)

	return DEFAULT_LEAD_OPPORTUNITY_FIELD_MAPPINGS


def move_to_opportunity(phone, products=None, purpose_lead=None, expected_delivery_date=None):
	if not phone or (not products and not purpose_lead and not expected_delivery_date):
		return

	from erpnext.utilities.phone_utils import search_doc_by_phone

	party_type, party_name = search_doc_by_phone(phone)
	if not (party_type and party_name):
		return

	opportunities = frappe.get_all(
		"Opportunity",
		filters={
			"opportunity_from": party_type,
			"party_name": party_name,
			"status": ["not in", ["Won", "Lost"]],
		},
		order_by="creation desc",
		limit=1,
	)

	if opportunities:
		max_retries_opp = 3
		for attempt in range(max_retries_opp):
			try:
				opp_doc = frappe.get_doc("Opportunity", opportunities[0].name)
				updated = False

				if products:
					existing_opp_prods = {
						item.product_type for item in opp_doc.get("preferred_product_type", [])
					}
					for p in products:
						if p.name not in existing_opp_prods:
							opp_doc.append("preferred_product_type", {"product_type": p.name})
							updated = True

				if purpose_lead and opp_doc.purpose_lead != purpose_lead:
					opp_doc.purpose_lead = purpose_lead
					updated = True

				if expected_delivery_date and opp_doc.expected_delivery_date != expected_delivery_date:
					opp_doc.expected_delivery_date = expected_delivery_date
					updated = True

				if updated:
					opp_doc.save(ignore_permissions=True)
					frappe.db.commit()
				break
			except frappe.TimestampMismatchError:
				if attempt < max_retries_opp - 1:
					time.sleep(1)
					continue
			except Exception:
				frappe.log_error("Opportunity Update Failed", frappe.get_traceback())
				break
