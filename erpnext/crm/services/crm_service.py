# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, add_days


@frappe.whitelist()
def link_lead_and_campaign(sales_order, commit=False):
	"""
	Link lead from customer and campaign from lead to a Sales Order.
	Accepts either a Sales Order docname (str) or a Document object.

	If called via API (docname str), persists changes and optionally commits.
	If called during doc validation (Document object), mutates doc in-memory.
	"""
	is_api_call = isinstance(sales_order, str)

	if is_api_call:
		doc = frappe.get_doc("Sales Order", sales_order)
	else:
		doc = sales_order

	modified = False

	# 1. Resolve lead from customer
	if not doc.lead and doc.customer:
		lead_name = frappe.db.get_value("Customer", doc.customer, "lead_name")
		if lead_name:
			doc.lead = lead_name
			modified = True

	# 2. Resolve campaign from lead
	if not doc.campaign and doc.lead:
		campaign_name = frappe.db.get_value("Lead", doc.lead, "campaign_name")
		if campaign_name:
			doc.campaign = campaign_name
			modified = True

	# 3. If called remotely / standalone via API
	if is_api_call and modified:
		doc.db_set("lead", doc.lead)
		doc.db_set("campaign", doc.campaign)
		if commit or getattr(frappe, "request", None):
			frappe.db.commit()

	return {
		"sales_order": doc.name,
		"lead": doc.lead,
		"campaign": doc.campaign,
		"modified": modified,
	}


@frappe.whitelist()
def check_koc_eligibility(sales_order):
	"""
	Check if a Sales Order is eligible for KOC commission based on the KOC's attribution window.
	Rule: sales_order.transaction_date between lead.creation and (lead.creation + attribution_window_days).
	Default attribution window: 30 days (configurable on DocType KOC).
	"""
	if isinstance(sales_order, str):
		so_data = frappe.db.get_value(
			"Sales Order",
			sales_order,
			["name", "customer", "lead", "campaign", "transaction_date", "grand_total", "docstatus"],
			as_dict=True,
		)
	else:
		so_data = sales_order

	if not so_data:
		return {"eligible": False, "reason": "Sales Order not found"}

	if so_data.get("docstatus") == 2:
		return {"eligible": False, "reason": "Sales Order is cancelled"}

	lead_id = so_data.get("lead")
	if not lead_id and so_data.get("customer"):
		lead_id = frappe.db.get_value("Customer", so_data["customer"], "lead_name")

	if not lead_id:
		return {"eligible": False, "reason": "No linked Lead"}

	lead_data = frappe.db.get_value(
		"Lead",
		lead_id,
		["name", "koc", "campaign_name", "creation", "first_reach_at"],
		as_dict=True,
	)

	if not lead_data or not lead_data.get("koc"):
		return {"eligible": False, "reason": "Lead is not attributed to any KOC"}

	koc_id = lead_data["koc"]
	window_days = frappe.db.get_value("KOC", koc_id, "attribution_window_days") or 30

	start_date = getdate(lead_data.get("first_reach_at") or lead_data.get("creation"))
	cutoff_date = add_days(start_date, int(window_days))
	order_date = getdate(so_data.get("transaction_date"))

	is_eligible = start_date <= order_date <= cutoff_date

	return {
		"eligible": is_eligible,
		"koc": koc_id,
		"lead": lead_id,
		"order_date": str(order_date),
		"lead_start_date": str(start_date),
		"cutoff_date": str(cutoff_date),
		"attribution_window_days": window_days,
		"commission_rate": 0.05,
		"estimated_commission": round(float(so_data.get("grand_total", 0)) * 0.05, 0) if is_eligible else 0,
	}
