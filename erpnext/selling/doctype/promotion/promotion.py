# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Promotion(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		is_expired: DF.Check
		priority: DF.Literal["", "G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7"]
		scope: DF.Literal["Line Item", "Order"]
		title: DF.Data
		type: DF.Literal["Percentage", "Fix Amount", "Gift"]
	# end: auto-generated types
	pass
