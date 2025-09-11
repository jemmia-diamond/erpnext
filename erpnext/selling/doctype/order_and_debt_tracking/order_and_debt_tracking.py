# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class OrderandDebtTracking(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		added_by: DF.Link | None
		added_on: DF.Datetime | None
		date: DF.Date | None
		name: DF.Int | None
		note: DF.LongText | None
		notify_to: DF.Link | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		status: DF.Literal["", "Waiting for Customer Pickup", "Waiting for Product", "Delayed / Postponed"]
	# end: auto-generated types

	def after_insert(self):
		self.update_added_by()

	def update_added_by(self):
		if not self.added_by:
			self.added_by = frappe.session.user