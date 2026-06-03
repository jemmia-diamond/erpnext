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
		progress_status: DF.Literal["", "\u0110\u1ee7 h\u00e0ng \u2013 kh\u00e1ch s\u1ebd nh\u1eadn tu\u1ea7n t\u1edbi", "\u0110\u1ee7 h\u00e0ng \u2013 kh\u00e1ch ch\u01b0a ch\u1ed1t ng\u00e0y nh\u1eadn", "Ch\u01b0a \u0111\u1ee7 h\u00e0ng", "\u0110\u00e3 giao \u2013 ch\u01b0a thu \u0111\u1ee7 ti\u1ec1n"]
		status: DF.Literal["", "Waiting for Customer Pickup", "Waiting for Product", "Delayed / Postponed"]
		status_reason: DF.Literal["", "Kh\u00e1ch \u0111\u00e3 ch\u1ed1t ng\u00e0y \u0111\u1ebfn nh\u1eadn t\u1ea1i c\u1eeda h\u00e0ng", "Sale s\u1ebd giao t\u1eadn n\u01a1i cho kh\u00e1ch", "G\u1eedi \u0111\u01a1n v\u1ecb v\u1eadn chuy\u1ec3n (COD) v\u1ec1 \u0111\u1ecba ch\u1ec9 kh\u00e1ch", "Kh\u00e1ch ch\u01b0a h\u1eb9n ng\u00e0y nh\u1eadn c\u1ee5 th\u1ec3, sale \u0111ang care th\u00eam", "Kh\u00e1ch b\u1eadn (c\u00f4ng t\u00e1c, n\u01b0\u1edbc ngo\u00e0i, du l\u1ecbch...)", "Kh\u00e1ch ch\u01b0a \u0111\u1ee7 ti\u1ec1n / \u0111ang gom ti\u1ec1n", "\u0110\u01a1n qu\u00e1 h\u1ea1n c\u00f4ng n\u1ee3, \u0111\u00e3 l\u00e0m \u0111\u1ec1 xu\u1ea5t gia h\u1ea1n", "\u0110ang gia c\u00f4ng", "\u0110\u1ee3i qu\u00e0 t\u1eb7ng", "Kh\u00e1ch ch\u1edd nh\u1eadn c\u00f9ng c\u00e1c \u0111\u01a1n kh\u00e1c", "H\u00e0ng l\u1ed7i, \u0111ang b\u1ea3o h\u00e0nh t\u1ea1i x\u01b0\u1edfng", "\u0110\u00e3 giao h\u00e0ng nh\u01b0ng ch\u01b0a thanh to\u00e1n \u0111\u1ee7 (qu\u1ea3n l\u00fd \u0111\u00e3 duy\u1ec7t)"]
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
