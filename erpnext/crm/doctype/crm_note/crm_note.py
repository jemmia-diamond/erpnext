# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CRMNote(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		added_by: DF.Link | None
		added_on: DF.Datetime | None
		from_platform: DF.Data | None
		name: DF.Int | None
		note: DF.TextEditor | None
		notify_to: DF.Link | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		type: DF.Literal["Status Update", "Customer Persona", "Products of Interest", "Store Visit", "C\\u1eadp nh\\u1eadt hi\\u1ec7n tr\\u1ea1ng", "System", "Other", "Ch\\u00e2n dung kh\\u00e1ch h\\u00e0ng", "X\\u1eed l\\u00fd t\\u1eeb ch\\u1ed1i", "Kh\\u00e1c", "Customer Profile", "Objection Handling"]
	# end: auto-generated types

	def update_added_by(self):
		if not self.added_by:
			self.added_by = frappe.session.user

	def on_update(self):
		self.sync_parent_opportunity_note_count()

	def on_trash(self):
		self.sync_parent_opportunity_note_count()

	def sync_parent_opportunity_note_count(self):
		if self.parenttype == "Opportunity" and self.parent:
			try:
				dates = frappe.db.sql(
					"""
					SELECT DISTINCT DATE(added_on) AS note_date
					FROM `tabCRM Note`
					WHERE parent = %(parent)s
					  AND parenttype = 'Opportunity'
					  AND added_on IS NOT NULL
					""",
					{"parent": self.parent},
					as_dict=True,
				)
				frappe.db.set_value("Opportunity", self.parent, "note_count", len(dates), update_modified=False)
			except Exception:
				pass
