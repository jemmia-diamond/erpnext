# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SalesOrderReference(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		sales_order: DF.Link | None
	# end: auto-generated types
	def validate(self):
		if self.sales_order and not self.order_number:
			self.order_number = frappe.db.get_value("Sales Order", self.sales_order, "order_number")

