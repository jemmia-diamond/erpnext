import json
import re

import frappe
from frappe.model.document import Document


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
	prev_sales_order: str
	new_order_code: str
	submitted_date: str
	items: list
	products_info: str

	def validate(self):
		self.process_products_info()

	def process_products_info(self):
		if not self.products_info:
			return

		try:
			products = json.loads(self.products_info)
			if not isinstance(products, list):
				frappe.throw(f"Invalid products_info in BuybackExchange {self.name}: Expected a list of products.")

			if self.items:
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
				if not self.prev_sales_order and row.prev_sales_order:
					self.prev_sales_order = row.prev_sales_order

		except Exception as e:
			frappe.log_error(f"Invalid products_info in BuybackExchange {self.name}: {e!s}", self.products_info)
			frappe.throw(f"Invalid products_info JSON in BuybackExchange {self.name}. Please check data from Lark.")

	def resolve_item_reference(self, row):
		"""
		Attempt to match the buyback item to a previous Sales Order Item.
		Heuristics:
		1. If phone number is available:
			- Search for Sales Order Items linked to this customer (by phone).
			- For GIA items (code starts with 'GIA'), matches against 'sku' field using LIKE.
			- For non-GIA items, matches against 'barcode' field using exact match.
			- Sorts candidates by transaction date descending.
		2. If ambiguity (multiple matches):
			- Attempts to narrow down by matching numeric part of 'order_code' in the payload
				against the 'order_number' or 'sales_order' name suffix.
		3. Fallback (if no phone or no match by phone):
			- Looks up Sales Order directly by 'order_code'.
			- Tries to find the item within that order.
		"""
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
					frappe.log_error(f"Ambiguous buyback item for {self.phone_number} / {row.item_code} with {len(candidates)} candidates", str(candidates))
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
		Patterns checked:
		- Exact match of original raw code
		- ORDER{number}
		- {number} (suffix match via LIKE)
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
