# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, add_days, get_datetime, now_datetime
from frappe.utils.password import passlibctx


from erpnext.utilities.phone_utils import get_phone_variants


def resolve_koc_record(identifier):
	"""
	Resolve a KOC document by portal_id, phone (with variants), or name (primary key).
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

	# 3. Direct search by phone variants (e.g. 090..., 8490..., +8490...)
	if not koc_name:
		variants = get_phone_variants(identifier, for_search=True)
		if variants:
			koc_name = frappe.db.get_value("KOC", {"phone": ["in", variants]}, "name")

	# 4. Search within comma-separated slugs
	if not koc_name:
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


@frappe.whitelist()
def verify_koc_login(identifier, password=None):
	"""
	Authenticate a KOC by portal_id / phone / name and password.
	Returns KOC profile on success.
	"""
	koc = resolve_koc_record(identifier)
	if not koc:
		return {
			"authenticated": False,
			"error": "invalid_credentials",
			"message": _("Tên đăng nhập hoặc mật khẩu không chính xác"),
		}

	# Check password if configured
	real_password = None
	try:
		real_password = koc.get_password("portal_password", raise_exception=False)
	except Exception:
		pass

	if not real_password and getattr(koc, "portal_password", None):
		if not koc.is_dummy_password(koc.portal_password):
			real_password = koc.portal_password

	if real_password:
		if not password:
			return {
				"authenticated": False,
				"error": "invalid_credentials",
				"message": _("Tên đăng nhập hoặc mật khẩu không chính xác"),
			}

		is_valid = False
		try:
			is_valid = passlibctx.verify(password, real_password)
		except Exception:
			pass

		if not is_valid:
			is_valid = (real_password == password)

		if not is_valid:
			return {
				"authenticated": False,
				"error": "invalid_credentials",
				"message": _("Tên đăng nhập hoặc mật khẩu không chính xác"),
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

	res_items = []
	for camp in campaigns:
		st = get_datetime(camp["start_time"]) if camp.get("start_time") else None
		et = get_datetime(camp["end_time"]) if camp.get("end_time") else None
		camp["start_time"] = st.strftime("%Y-%m-%dT%H:%M:%SZ") if st else None
		camp["end_time"] = et.strftime("%Y-%m-%dT%H:%M:%SZ") if et else None
		camp["commission_rate"] = float(camp.get("commission_rate") or 0)
		res_items.append(camp)

	return {"items": res_items}


@frappe.whitelist()
def get_koc_dashboard_stats(identifier, session_id=None):
	"""
	Aggregated metrics for the 5 stat cards:
	- recorded_leads
	- ordered_leads
	- active_leads
	- total_order_value
	- commission_earned
	Runs in 1 optimized aggregation pass.
	"""
	koc = resolve_koc_record(identifier)
	if not koc:
		frappe.throw(_("KOC not found"), frappe.DoesNotExistError)

	koc_id = koc.name
	window_days = int(koc.attribution_window_days or 45)
	default_koc_rate = float(koc.commission_rate or 0)

	if session_id in ("all", "", None):
		session_id = None

	query = """
		SELECT 
			l.name AS id,
			l.creation AS recorded_at,
			l.first_reach_at,
			ck.commission_rate AS campaign_commission_rate,
			so.name AS order_id,
			so.transaction_date AS order_date,
			COALESCE(so.grand_total, 0) AS order_value
		FROM `tabLead` l
		LEFT JOIN `tabCampaign` c ON c.name = l.campaign_name
		LEFT JOIN `tabCampaign KOC` ck ON ck.parent = l.campaign_name AND ck.koc = %(koc)s
		LEFT JOIN `tabCustomer` cust ON (
			cust.lead_name = l.name 
			OR (l.customer IS NOT NULL AND cust.name = l.customer)
			OR (l.phone IS NOT NULL AND (cust.mobile_no = l.phone OR cust.mobile_no = REPLACE(l.phone, '+84', '0') OR cust.phone = l.phone))
		)
		LEFT JOIN `tabSales Order` so ON (
			so.lead = l.name 
			OR (cust.name IS NOT NULL AND so.customer = cust.name)
			OR (l.customer IS NOT NULL AND so.customer = l.customer)
		)
		WHERE l.koc = %(koc)s
	"""
	params = {
		"koc": koc_id,
		"default_rate": default_koc_rate,
		"session_id": session_id,
	}

	if session_id:
		query += " AND (l.campaign_name = %(session_id)s OR c.name = %(session_id)s) "

	rows = frappe.db.sql(query, params, as_dict=True)

	# Deduplicate leads keeping best order
	leads_dict = {}
	for r in rows:
		lid = r["id"]
		if lid not in leads_dict or (r.get("order_value") or 0) > (leads_dict[lid].get("order_value") or 0):
			leads_dict[lid] = r

	today = getdate(now_datetime())
	recorded_leads = len(leads_dict)
	ordered_leads = 0
	active_leads = 0
	total_order_val = 0.0
	total_commission = 0.0

	for item in leads_dict.values():
		capture_date = getdate(item.get("first_reach_at") or item.get("recorded_at"))
		cutoff_date = add_days(capture_date, window_days)

		order_date = getdate(item["order_date"]) if item.get("order_date") else None
		has_order = bool(item.get("order_id") and order_date)
		order_in_window = has_order and (capture_date <= order_date <= cutoff_date)

		# Tiered commission rate: Campaign rate -> KOC timeline rate -> master fallback
		if item.get("campaign_commission_rate"):
			comm_rate = float(item["campaign_commission_rate"])
		else:
			comm_rate = koc.get_commission_rate(order_date or capture_date)

		order_val = float(item.get("order_value") or 0) if has_order else 0.0

		if order_in_window:
			ordered_leads += 1
			total_order_val += order_val
			total_commission += round(order_val * (comm_rate / 100.0), 0)
		elif today <= cutoff_date:
			active_leads += 1

	now_dt = now_datetime()
	return {
		"recorded_leads": recorded_leads,
		"ordered_leads": ordered_leads,
		"active_leads": active_leads,
		"active_window_days": window_days,
		"total_order_value": int(total_order_val),
		"commission_earned": int(total_commission),
		"last_updated": now_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
	}


@frappe.whitelist()
def get_koc_leads(identifier, session_id=None, page=1, page_size=10, status=None):
	"""
	Paginated lead list with server-side pagination (LIMIT & OFFSET).
	Computes 45-day window status & commission ONLY for the requested page slice!
	"""
	koc = resolve_koc_record(identifier)
	if not koc:
		frappe.throw(_("KOC not found"), frappe.DoesNotExistError)

	koc_id = koc.name
	window_days = int(koc.attribution_window_days or 45)
	default_koc_rate = float(koc.commission_rate or 0)
	page = max(1, int(page or 1))
	page_size = max(1, min(100, int(page_size or 10)))
	offset = (page - 1) * page_size

	if session_id in ("all", "", None):
		session_id = None

	params = {
		"koc": koc_id,
		"default_rate": default_koc_rate,
		"session_id": session_id,
		"limit": page_size,
		"offset": offset,
	}

	session_filter = ""
	if session_id:
		session_filter = " AND (l.campaign_name = %(session_id)s OR c.name = %(session_id)s) "

	# 1. Get total count for pagination
	count_query = f"""
		SELECT COUNT(DISTINCT l.name) AS total
		FROM `tabLead` l
		LEFT JOIN `tabCampaign` c ON c.name = l.campaign_name
		WHERE l.koc = %(koc)s {session_filter}
	"""
	total_result = frappe.db.sql(count_query, params, as_dict=True)
	total_leads = total_result[0]["total"] if total_result else 0

	# 2. Get distinct lead IDs for ONLY the current page slice
	page_ids_query = f"""
		SELECT l.name
		FROM `tabLead` l
		LEFT JOIN `tabCampaign` c ON c.name = l.campaign_name
		WHERE l.koc = %(koc)s {session_filter}
		ORDER BY l.creation DESC
		LIMIT %(limit)s OFFSET %(offset)s
	"""
	lead_rows = frappe.db.sql(page_ids_query, params, as_dict=True)
	page_lead_ids = [r["name"] for r in lead_rows]

	if not page_lead_ids:
		return {
			"items": [],
			"total": total_leads,
			"page": page,
			"page_size": page_size,
		}

	# 3. Fetch full lead + order data ONLY for the current page rows
	leads_query = """
		SELECT 
			l.name AS id,
			l.lead_name,
			l.phone,
			l.campaign_name AS session_id,
			COALESCE(c.campaign_name, l.campaign_name) AS session_name,
			l.creation AS recorded_at,
			l.first_reach_at,
			l.modified AS updated_at,
			ck.commission_rate AS campaign_commission_rate,
			so.name AS order_id,
			so.transaction_date AS order_date,
			COALESCE(so.grand_total, 0) AS order_value
		FROM `tabLead` l
		LEFT JOIN `tabCampaign` c ON c.name = l.campaign_name
		LEFT JOIN `tabCampaign KOC` ck ON ck.parent = l.campaign_name AND ck.koc = %(koc)s
		LEFT JOIN `tabCustomer` cust ON (
			cust.lead_name = l.name 
			OR (l.customer IS NOT NULL AND cust.name = l.customer)
			OR (l.phone IS NOT NULL AND (cust.mobile_no = l.phone OR cust.mobile_no = REPLACE(l.phone, '+84', '0') OR cust.phone = l.phone))
		)
		LEFT JOIN `tabSales Order` so ON (
			so.lead = l.name 
			OR (cust.name IS NOT NULL AND so.customer = cust.name)
			OR (l.customer IS NOT NULL AND so.customer = l.customer)
		)
		WHERE l.name IN %(lead_ids)s
		ORDER BY l.creation DESC
	"""
	lead_details = frappe.db.sql(
		leads_query,
		{
			"koc": koc_id,
			"default_rate": default_koc_rate,
			"lead_ids": tuple(page_lead_ids),
		},
		as_dict=True,
	)

	# Deduplicate multiple orders per lead
	leads_dict = {}
	for r in lead_details:
		lid = r["id"]
		if lid not in leads_dict or (r.get("order_value") or 0) > (leads_dict[lid].get("order_value") or 0):
			leads_dict[lid] = r

	today = getdate(now_datetime())
	items = []

	# Maintain the exact page order
	for lid in page_lead_ids:
		if lid not in leads_dict:
			continue
		item = leads_dict[lid]

		capture_date = getdate(item.get("first_reach_at") or item.get("recorded_at"))
		cutoff_date = add_days(capture_date, window_days)
		item["window_end"] = str(cutoff_date)

		order_date = getdate(item["order_date"]) if item.get("order_date") else None
		has_order = bool(item.get("order_id") and order_date)
		order_in_window = has_order and (capture_date <= order_date <= cutoff_date)

		# Tiered commission rate: Campaign rate -> KOC timeline rate -> master fallback
		if item.get("campaign_commission_rate"):
			comm_rate = float(item["campaign_commission_rate"])
		else:
			comm_rate = koc.get_commission_rate(order_date or capture_date)

		order_val = float(item.get("order_value") or 0) if has_order else 0.0

		if order_in_window:
			status_kind = "in_order"
			status_label = "Đã ra đơn trong hạn"
			sub_label = f"Hạn đến {cutoff_date.strftime('%d/%m/%Y')}"
			comm_earned = round(order_val * (comm_rate / 100.0), 0)
		elif today <= cutoff_date:
			status_kind = "active"
			status_label = "Còn hạn"
			sub_label = f"Hạn đến {cutoff_date.strftime('%d/%m/%Y')}"
			comm_earned = 0.0
		else:
			status_kind = "expired"
			status_label = f"Quá hạn {window_days} ngày"
			sub_label = f"Đã hết hạn {cutoff_date.strftime('%d/%m/%Y')}"
			comm_earned = 0.0

		# Format timestamps to standard ISO 8601 UTC string
		rec_at = get_datetime(item.get("recorded_at")) if item.get("recorded_at") else None
		upd_at = get_datetime(item.get("updated_at")) if item.get("updated_at") else None

		item["recorded_at"] = rec_at.strftime("%Y-%m-%dT%H:%M:%SZ") if rec_at else None
		item["updated_at"] = upd_at.strftime("%Y-%m-%dT%H:%M:%SZ") if upd_at else None
		item["commission_rate"] = comm_rate

		item["status"] = {
			"kind": status_kind,
			"label": status_label,
			"sub_label": sub_label,
		}
		item["commission"] = int(comm_earned)
		item["order_value"] = int(order_val)
		items.append(item)

	return {
		"items": items,
		"total": total_leads,
		"page": page,
		"page_size": page_size,
	}


@frappe.whitelist()
def get_koc_dashboard_data(identifier, session_id=None, page=1, page_size=10):
	"""
	Convenience composite endpoint calling stats + sessions + page 1 leads in 1 call.
	"""
	koc = resolve_koc_record(identifier)
	if not koc:
		frappe.throw(_("KOC not found"), frappe.DoesNotExistError)

	return {
		"koc": {
			"id": koc.portal_id or koc.name,
			"name": koc.full_name or koc.portal_id or koc.name,
			"koc_docname": koc.name,
			"attribution_window_days": koc.attribution_window_days or 45,
			"default_commission_rate": float(koc.commission_rate or 0),
		},
		"sessions": get_koc_sessions(identifier).get("items", []),
		"stats": get_koc_dashboard_stats(identifier, session_id=session_id),
		"leads": get_koc_leads(identifier, session_id=session_id, page=page, page_size=page_size),
	}
