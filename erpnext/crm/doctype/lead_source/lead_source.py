# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


# import frappe
from frappe.model.document import Document


class LeadSource(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		details: DF.TextEditor | None
		pancake_page_id: DF.Data | None
		pancake_platform: DF.Data | None
		source_name: DF.Data
	# end: auto-generated types

	pass
