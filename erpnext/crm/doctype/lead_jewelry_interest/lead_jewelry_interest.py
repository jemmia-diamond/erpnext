# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class LeadJewelryInterest(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		design_description: DF.SmallText | None
		diamond_specifications: DF.Data | None
		estimate_value: DF.Float
		jewelry_material: DF.Literal["18K", "14K"]
		jewelry_type: DF.Data | None
		offline_budget: DF.Float
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		purchase_date: DF.Date | None
		purpose: DF.Link | None
		size: DF.Float
		stone_shape: DF.Literal["Round", "Princess", "Asscher", "Emerald", "Marquise", "Oval", "Radiant", "Pear", "Heart", "Cushion", "Baguette"]
		stone_type: DF.Literal["Kim c\u01b0\u01a1ng t\u1ef1 nhi\u00ean", "Moissanite", "Kim c\u01b0\u01a1ng t\u1ef1 nhi\u00ean & Moissanite"]
	# end: auto-generated types

	pass
