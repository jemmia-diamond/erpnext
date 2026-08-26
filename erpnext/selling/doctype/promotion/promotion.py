# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
import frappe
import requests
import json
from frappe.model.document import Document
from frappe.utils import getdate, nowdate
from erpnext.config.config import config
from frappe.query_builder import DocType
from frappe.query_builder.functions import IfNull, Lower
from frappe.utils import get_first_day, get_last_day


class Promotion(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		bizfly_id: DF.Data | None
		description: DF.LongText | None
		discount_amount: DF.Currency
		discount_percent: DF.Percent
		discount_type: DF.Literal["Percentage", "Fix Amount", "Gift"]
		end_date: DF.Date | None
		is_active: DF.Check
		is_expired: DF.Check
		max_value: DF.Float
		min_value: DF.Float
		priority: DF.Literal["", "G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7"]
		product_category: DF.Literal["Kim Cương Viên", "Vỏ Trang Sức", "Khác"]
		promotion_group: DF.Link | None
		promotion_month: DF.Link | None
		scope: DF.Literal["Line Item", "Order"]
		start_date: DF.Date
		title: DF.Data
		promotion_type: DF.Literal["Khuyến mãi nền", "Khác"]
	# end: auto-generated types
	pass

def update_promotion_status():
	today = nowdate()

	frappe.db.sql("""
		UPDATE `tabPromotion`
		SET is_active = 0
		WHERE end_date < %s AND is_active = 1
	""", (today,))

	frappe.db.sql("""
		UPDATE `tabPromotion`
		SET is_active = 1
		WHERE start_date <= %s
		AND (end_date >= %s OR end_date IS NULL)
		AND is_active = 0
	""", (today, today))

	frappe.db.sql("""
		UPDATE `tabPromotion`
		SET is_active = 0
		WHERE start_date > %s AND is_active = 1
	""", (today,))

@frappe.whitelist()
def sync_diamond_collect():
	url = f"{config.FN_BASE_URL}/api/erp/promotions/diamond-collects"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {config.FN_BEARER_TOKEN}",
	}

	try:
		response = requests.post(url=url, headers=headers, json={})
		response.raise_for_status()

		try:
			return response.json().get("message", "Đồng bộ thành công")
		except json.JSONDecodeError:
			return response.text

	except Exception as e:
		frappe.log_error(f"Sync Diamond Collect failed: {e!s}")
		frappe.throw(f"Đồng bộ thất bại: {e!s}")

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def promotion_query(doctype, txt, searchfield, start, page_len, filters):
	filters = filters or {}
	transaction_date = filters.get("transaction_date")
	real_order_date = filters.get("real_order_date")
	scope = filters.get("scope") or "Line Item"
	show_all = filters.get("show_all")
	txt_lower = f"%{txt.lower()}%" if txt else "%"

	order_date = real_order_date or transaction_date

	# Case 1: Checked "Show All" [✔] -> Show from real_order_date till now (active today OR ended on/after order date)
	if show_all in (1, "1"):
		if order_date:
			date_filter_sql = """(
				is_active = 1
				OR (end_date IS NULL OR EXTRACT(YEAR_MONTH FROM end_date) >= EXTRACT(YEAR_MONTH FROM %(order_date)s))
			)"""
		else:
			date_filter_sql = "1=1"

	# Case 2: Unchecked "Show All" [ ] (Default) -> ONLY promotions for real_order_date (ignore is_active)
	else:
		if order_date:
			date_filter_sql = """(
				EXTRACT(YEAR_MONTH FROM start_date) <= EXTRACT(YEAR_MONTH FROM %(order_date)s)
				AND (end_date IS NULL OR EXTRACT(YEAR_MONTH FROM end_date) >= EXTRACT(YEAR_MONTH FROM %(order_date)s))
			)"""
		else:
			date_filter_sql = "is_active = 1"

	results = frappe.db.sql(f"""
		SELECT name, ifnull(title, name) as title
		FROM `tabPromotion`
		WHERE docstatus < 2
		AND scope = %(scope)s
		AND {date_filter_sql}
		AND (LOWER(name) LIKE %(txt)s OR LOWER(title) LIKE %(txt)s)
		ORDER BY modified DESC
		LIMIT %(start)s, %(page_len)s
	""", {
		"scope": scope,
		"order_date": order_date,
		"txt": txt_lower,
		"start": start,
		"page_len": page_len
	}, as_dict=True if filters.get("as_dict") else False)

	return results


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def promotion_query_qb(doctype, txt, searchfield, start, page_len, filters):
	filters = filters or {}
	transaction_date = filters.get("transaction_date")
	real_order_date = filters.get("real_order_date")
	scope = filters.get("scope") or "Line Item"
	show_all = filters.get("show_all")
	as_dict = bool(filters.get("as_dict"))
	order_date = real_order_date or transaction_date
	Promotion = DocType("Promotion")

	query = (
		frappe.qb.from_(Promotion)
		.select(Promotion.name, IfNull(Promotion.title, Promotion.name).as_("title"))
		.where(Promotion.docstatus < 2)
		.where(Promotion.scope == scope)
	)

	if show_all in (1, "1"):
		if order_date:
			m_start = get_first_day(order_date)
			query = query.where(
				(Promotion.is_active == 1) | (Promotion.end_date.isnull() | (Promotion.end_date >= m_start))
			)
	else:
		if order_date:
			m_start = get_first_day(order_date)
			m_end = get_last_day(order_date)
			query = query.where(
				(Promotion.start_date <= m_end)
				& (Promotion.end_date.isnull() | (Promotion.end_date >= m_start))
			)
		else:
			query = query.where(Promotion.is_active == 1)

	if txt:
		txt_lower = f"%{txt.lower()}%"
		query = query.where(
			(Lower(Promotion.name).like(txt_lower)) | (Lower(Promotion.title).like(txt_lower))
		)

	query = query.orderby(Promotion.modified, order=frappe.qb.desc).offset(start).limit(page_len)

	return query.run(as_dict=as_dict)
