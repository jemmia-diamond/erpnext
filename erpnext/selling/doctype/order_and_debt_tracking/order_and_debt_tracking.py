# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model.document import Document


class OrderandDebtTracking(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		added_by: DF.Link | None
		added_on: DF.Datetime | None
		amended_from: DF.Link | None
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
		self._notify_assigned_user()

	def update_added_by(self):
		if not self.added_by:
			self.added_by = frappe.session.user

	def _notify_assigned_user(self):
		if not self.notify_to:
			return
		
		user_info = frappe.db.get_value("User", self.notify_to, ["email", "enabled", "language"], as_dict=True)
		if not user_info or not user_info.enabled:
			return
		recipient = user_info.email or self.notify_to

		order_number = frappe.db.get_value("Sales Order", self.parent, "order_number") or self.parent

		notification_doc = {
			"type": "Assignment",
			"document_type": self.parenttype,
			"document_name": self.parent,
			"subject": frappe._(
				"Debt note on Sales Order {0} by {1}".format(
					order_number,
					self.added_by or frappe.session.user,
				)
			),
			"from_user": self.added_by or frappe.session.user,
			"email_content": f"<div>{frappe.as_unicode(self.note or '')}</div>",
		}
		enqueue_create_notification(recipient, notification_doc)