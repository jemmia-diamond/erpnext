import json
import re

import frappe
from frappe.model.document import Document

from erpnext.selling.doctype.sales_order.sales_order import (
	_update_sales_order_return_amount,
)


class BuybackExchange(Document):
	lark_instance_id: str
	instance_type: str
	status: str
	customer_name: str
	phone_number: str
	national_id: str
	reason: str
	refund_amount: float
	order_code: str
	new_order_code: str
	submitted_date: str
	items: list
	products_info: str
	serial_number: str

	def validate(self):
		self.process_products_info()
		if self.is_new():
			self.link_to_current_sales_order()

	def link_to_current_sales_order(self):
		if not self.new_order_code:
			return

		sales_order = self.find_sales_order(self.new_order_code)
		if sales_order:
			for item in self.items:
				item.current_sales_order = sales_order

	def on_update(self):
		sales_orders = {item.current_sales_order for item in self.items if item.current_sales_order}
		for so in sales_orders:
			_update_sales_order_return_amount(so)

	def process_products_info(self):
		if not self.products_info:
			return

		try:
			products = json.loads(self.products_info)
			if not isinstance(products, list):
				frappe.throw(frappe._("Invalid products_info in BuybackExchange {0}: Expected a list of products.").format(self.name))

			if not self.is_new():
				if frappe.db.exists("Buyback Exchange Item", {"parent": self.name}):
					return
			elif self.items:
				return

			for product in products:
				row = self.append("items", {})

				row.product_name = product.get("product_name")
				row.item_code = product.get("code")
				row.sale_price = product.get("sale_price")
				row.buyback_percentage = product.get("buyback_percentage")
				row.calculated_buyback_price = product.get("calculated_buyback_price")
				row.buyback_price = product.get("buyback_price")
				row.order_code = product.get("order_code")

				self.resolve_item_reference(row)

				if not self.order_code and row.order_code:
					self.order_code = row.order_code

		except Exception as e:
			frappe.log_error(f"Invalid products_info in BuybackExchange {self.name}: {e!s}", self.products_info)
			frappe.throw(frappe._("Invalid products_info JSON in BuybackExchange {0}. Please check data from Lark.").format(self.name))

	def resolve_item_reference(self, row):
		if self.phone_number and row.item_code:
			is_gia = str(row.item_code).startswith("GIA")
			lookup_field = "sku" if is_gia else "barcode"
			operator = "LIKE" if is_gia else "="
			lookup_value = f"%{row.item_code}%" if is_gia else row.item_code

			candidates = frappe.db.sql(f"""
				SELECT soi.name as item_name, so.name as sales_order, so.order_number
				FROM `tabSales Order Item` soi
				JOIN `tabSales Order` so ON soi.parent = so.name
				WHERE (so.contact_mobile = %s OR so.contact_phone = %s)
				AND soi.{lookup_field} {operator} %s
				ORDER BY so.transaction_date DESC
			""", (self.phone_number, self.phone_number, lookup_value), as_dict=True)

			if candidates:
				selected = None

				if len(candidates) == 1:
					selected = candidates[0]
				else:
					frappe.logger().info(
						frappe._("Ambiguous buyback item for {0} / {1} with {2} candidates: {3}").format(
							self.phone_number, row.item_code, len(candidates), str(candidates)
						)
					)
					if row.order_code:
						normalized_input = re.search(r'(\d+)', str(row.order_code))
						if normalized_input:
							num_val = int(normalized_input.group(1))
							for cand in candidates:
								cand_num_match = re.search(r'(\d+)', str(cand.order_number or ""))
								if cand_num_match and int(cand_num_match.group(1)) == num_val:
									selected = cand
									break

								so_num_match = re.search(r'(\d+)$', str(cand.sales_order))
								if so_num_match and int(so_num_match.group(1)) == num_val:
									selected = cand
									break

				if selected:
					row.prev_sales_order = selected["sales_order"]
					row.prev_sales_order_item = selected["item_name"]
					return

				return

		if row.order_code:
			sales_order = self.find_sales_order(row.order_code)
			if sales_order:
				row.prev_sales_order = sales_order
				if row.item_code:
					item_name = frappe.db.get_value("Sales Order Item",
						{"parent": sales_order, "item_code": row.item_code}, "name")

					if not item_name:
						is_gia = str(row.item_code).startswith("GIA") if row.item_code else False
						if is_gia:
							item_name = frappe.db.get_value("Sales Order Item",
								{"parent": sales_order, "sku": ["like", f"%{row.item_code}%"]}, "name")
						else:
							item_name = frappe.db.get_value("Sales Order Item",
								{"parent": sales_order, "barcode": row.item_code}, "name")

					if item_name:
						row.prev_sales_order_item = item_name

	def find_sales_order(self, raw_code):
		if not raw_code:
			return None

		number_part = self.extract_order_number(raw_code)
		if not number_part:
			so_name = frappe.db.get_value("Sales Order", {"order_number": raw_code}, "name")
			if so_name:
				return so_name
			return None

		return self.find_sales_order_by_number(number_part, raw_code)

	def extract_order_number(self, raw_code):
		"""Extracts the first numeric sequence from the order string."""
		match = re.search(r'(\d+)', str(raw_code))
		if match:
			return match.group(1)
		return None

	def find_sales_order_by_number(self, number_part, original_raw_code=None):
		"""
		Finds a Sales Order by loosely matching the order number token.
		"""
		if original_raw_code:
			if frappe.db.exists("Sales Order", {"order_number": original_raw_code}):
				return frappe.get_value("Sales Order", {"order_number": original_raw_code}, "name")

		patterns = [
			f"ORDER{number_part}",
			f"{number_part}",
		]

		for pattern in patterns:
			so_name = frappe.db.get_value("Sales Order", {"order_number": ["like", pattern]}, "name")
			if so_name:
				return so_name

		return None
