# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


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
