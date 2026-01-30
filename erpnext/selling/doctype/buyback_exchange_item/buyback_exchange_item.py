# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class BuybackExchangeItem(Document):
	product_name: str
	item_code: str
	order_code: str
	prev_sales_order: str
	prev_sales_order_item: str
	current_sales_order: str
	sale_price: float
	buyback_percentage: float
	calculated_buyback_price: float
	buyback_price: float
