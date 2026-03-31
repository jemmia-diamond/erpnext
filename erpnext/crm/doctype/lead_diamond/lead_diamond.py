# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class LeadDiamond(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		clarity: DF.Literal["IF", "VS1", "VS2", "VVS1", "VVS2"]
		color: DF.Literal["D", "E", "F", "G", "H"]
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		shape: DF.Literal["Round", "Princess", "Cushion", "Emerald", "Asscher", "Oval", "Marquise", "Radiant", "Pear", "Heart", "Trillion", "Baguette"]
		size: DF.Float
	# end: auto-generated types
	pass
