# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class SMSTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		branch_name: DF.Literal[None]
		content: DF.Text | None
		name1: DF.SmallText | None
		type: DF.Literal["Advertisement", "Customer Care"]
	# end: auto-generated types
	pass
