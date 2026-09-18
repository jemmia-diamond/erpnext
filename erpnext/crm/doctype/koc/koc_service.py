# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, add_days, get_datetime, now_datetime
from frappe.utils.password import passlibctx, check_password, update_password


def resolve_koc_record(identifier):
	"""
	Resolve a KOC document by portal_id, phone, or name (primary key).
	Fast indexed query.
	"""
	if not identifier:
		return None

	identifier = str(identifier).strip()

	# 1. Direct search by portal_id (unique index)
	koc_name = frappe.db.get_value("KOC", {"portal_id": identifier}, "name")

	# 2. Direct search by primary key name
	if not koc_name and frappe.db.exists("KOC", identifier):
		koc_name = identifier

	# 3. Direct search by phone (index)
	if not koc_name:
		koc_name = frappe.db.get_value("KOC", {"phone": identifier}, "name")

	# 4. Search within comma-separated slugs
	if not koc_name:
		# Check if identifier appears in slugs
		match = frappe.db.sql(
			"""
			SELECT name FROM `tabKOC`
			WHERE FIND_IN_SET(%(id)s, REPLACE(REPLACE(slugs, ' ', ''), '\n', ','))
			LIMIT 1
			""",
			{"id": identifier.lower()},
			as_dict=True,
		)
		if match:
			koc_name = match[0].name

	if not koc_name:
		return None

	return frappe.get_doc("KOC", koc_name)


@frappe.whitelist(allow_guest=True)
def verify_koc_login(identifier, password=None):
	"""
	Authenticate a KOC by portal_id / phone / name and password.
	Returns KOC profile on success.
	"""
	koc = resolve_koc_record(identifier)
	if not koc:
		return {
			"authenticated": False,
			"error": "invalid_user",
			"message": _("KOC identifier not found"),
		}

	# Check password if provided and configured
	if koc.portal_password:
		if not password:
			return {
				"authenticated": False,
				"error": "missing_password",
				"message": _("Password is required"),
			}
		# Verify password (can be stored via passlibctx or plain text check)
		try:
			is_valid = passlibctx.verify(password, koc.portal_password)
		except Exception:
			# Fallback for plain-text password set directly in desk
			is_valid = (koc.portal_password == password)

		if not is_valid:
			return {
				"authenticated": False,
				"error": "invalid_password",
				"message": _("Mật khẩu không đúng"),
			}

	return {
		"authenticated": True,
		"koc": {
			"id": koc.portal_id or koc.name,
			"name": koc.full_name or koc.portal_id or koc.name,
			"koc_docname": koc.name,
			"phone": koc.phone,
			"attribution_window_days": koc.attribution_window_days or 45,
			"commission_rate": float(koc.commission_rate or 0),
		},
	}


@frappe.whitelist()
def get_koc_sessions(identifier):
	"""
	Return all campaigns/livestreams where this KOC participates.
	Query joins Campaign and Campaign KOC (child table) in 1 shot.
	"""
	koc = resolve_koc_record(identifier)
	if not koc:
		return {"items": []}

	campaigns = frappe.db.sql(
		"""
		SELECT 
			c.name AS id,
			c.campaign_name AS name,
			c.start_time,
			c.end_time,
			c.platforms,
			COALESCE(ck.commission_rate, %(default_rate)s) AS commission_rate
		FROM `tabCampaign KOC` ck
		INNER JOIN `tabCampaign` c ON c.name = ck.parent
		WHERE ck.koc = %(koc)s
		ORDER BY c.start_time DESC, c.creation DESC
		""",
		{
			"koc": koc.name,
			"default_rate": float(koc.commission_rate or 0),
		},
		as_dict=True,
	)

	return {"items": campaigns}


@frappe.whitelist()
def get_koc_dashboard_data(identifier, session_id=None, page=1, page_size=20):
	"""
	Consolidated query returning:
	1. koc profile
	2. available sessions / campaigns
	3. aggregated stats (5 cards)
	4. paginated leads with order value & commission
	All in minimal round trips without N+1 queries.
	"""
	koc = resolve_koc_record(identifier)
	if not koc:
		frappe.throw(_("KOC not found"), frappe.DoesNotExistError)

	koc_id = koc.name
	window_days = int(koc.attribution_window_days or 45)
	default_koc_rate = float(koc.commission_rate or 0)
	page = max(1, int(page or 1))
	page_size = max(1, min(100, int(page_size or 20)))
	offset = (page - 1) * page_size

	# Normalize session_id
	if session_id in ("all", "", None):
		session_id = None

	# 1. Get KOC's Sessions (1 query)
	sessions = frappe.db.sql(
		"""
		SELECT 
			c.name AS id,
			c.campaign_name AS name,
			c.start_time,
			c.end_time,
			c.platforms,
			COALESCE(ck.commission_rate, %(default_rate)s) AS commission_rate
		FROM `tabCampaign KOC` ck
		INNER JOIN `tabCampaign` c ON c.name = ck.parent
		WHERE ck.koc = %(koc)s
		ORDER BY c.start_time DESC, c.creation DESC
		""",
		{"koc": koc_id, "default_rate": default_koc_rate},
		as_dict=True,
	)

	# 2. Query all leads in scope with their best Sales Order (1 joined query)
	# Note: To avoid duplicate rows when multiple orders exist, we join the highest value submitted Sales Order
	lead_query = """
		SELECT 
			l.name AS id,
			l.lead_name,
			l.phone,
			l.campaign_name AS session_id,
			COALESCE(c.campaign_name, l.campaign_name) AS session_name,
			l.creation AS recorded_at,
			l.first_reach_at,
			l.modified AS updated_at,
			COALESCE(ck.commission_rate, %(default_rate)s) AS commission_rate,
			so.name AS order_id,
			so.transaction_date AS order_date,
			COALESCE(so.grand_total, 0) AS order_value
		FROM `tabLead` l
		LEFT JOIN `tabCampaign` c ON c.name = l.campaign_name
		LEFT JOIN `tabCampaign KOC` ck ON ck.parent = l.campaign_name AND ck.koc = %(koc)s
		LEFT JOIN `tabSales Order` so ON (
			(so.lead = l.name OR (l.customer IS NOT NULL AND so.customer = l.customer))
			AND so.docstatus = 1
		)
		WHERE l.koc = %(koc)s
	"""
	params = {
		"koc": koc_id,
		"default_rate": default_koc_rate,
		"session_id": session_id,
	}

	if session_id:
		lead_query += " AND (l.campaign_name = %(session_id)s OR c.name = %(session_id)s) "

	lead_query += " ORDER BY l.creation DESC"

	all_leads_raw = frappe.db.sql(lead_query, params, as_dict=True)

	# Aggregate unique leads (in case multiple orders exist for one lead)
	leads_dict = {}
	for row in all_leads_raw:
		lid = row["id"]
		if lid not in leads_dict:
			leads_dict[lid] = row
		else:
			# If another order exists, pick the one with higher value
			if (row.get("order_value") or 0) > (leads_dict[lid].get("order_value") or 0):
				leads_dict[lid] = row

	leads_list = list(leads_dict.values())
	total_leads_count = len(leads_list)

	# Compute 45-day window status & commission for each lead
	today = getdate(now_datetime())
	ordered_leads_count = 0
	active_leads_count = 0
	total_order_val = 0.0
	total_comm_earned = 0.0

	for item in leads_list:
		capture_date = getdate(item.get("first_reach_at") or item.get("recorded_at"))
		cutoff_date = add_days(capture_date, window_days)
		item["window_end"] = str(cutoff_date)

		order_date = getdate(item["order_date"]) if item.get("order_date") else None
		has_order = bool(item.get("order_id") and order_date)
		order_in_window = has_order and (capture_date <= order_date <= cutoff_date)

		comm_rate = float(item.get("commission_rate") or 0)
		order_val = float(item.get("order_value") or 0) if has_order else 0.0

		if order_in_window:
			status_kind = "in_order"
			status_label = "Đã ra đơn trong hạn"
			sub_label = f"Hạn đến {cutoff_date.strftime('%d/%m/%Y')}"
			comm_earned = round(order_val * (comm_rate / 100.0), 0)
			ordered_leads_count += 1
			total_order_val += order_val
			total_comm_earned += comm_earned
		elif today <= cutoff_date:
			status_kind = "active"
			status_label = "Còn hạn"
			sub_label = f"Hạn đến {cutoff_date.strftime('%d/%m/%Y')}"
			comm_earned = 0.0
			active_leads_count += 1
		else:
			status_kind = "expired"
			status_label = f"Quá hạn {window_days} ngày"
			sub_label = f"Đã hết hạn {cutoff_date.strftime('%d/%m/%Y')}"
			comm_earned = 0.0

		item["status"] = {
			"kind": status_kind,
			"label": status_label,
			"sub_label": sub_label,
		}
		item["calculated_commission"] = comm_earned
		item["effective_order_value"] = order_val

	# Slice for pagination
	paginated_items = leads_list[offset : offset + page_size]

	stats = {
		"recorded_leads": total_leads_count,
		"ordered_leads": ordered_leads_count,
		"active_leads": active_leads_count,
		"active_window_days": window_days,
		"total_order_value": int(total_order_val),
		"commission_earned": int(total_comm_earned),
		"last_updated": str(now_datetime()),
	}

	return {
		"koc": {
			"id": koc.portal_id or koc.name,
			"name": koc.full_name or koc.portal_id or koc.name,
			"koc_docname": koc.name,
			"attribution_window_days": window_days,
			"default_commission_rate": default_koc_rate,
		},
		"sessions": sessions,
		"stats": stats,
		"leads": {
			"total": total_leads_count,
			"page": page,
			"page_size": page_size,
			"items": paginated_items,
		},
	}
