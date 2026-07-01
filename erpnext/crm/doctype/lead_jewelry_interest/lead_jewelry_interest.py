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

		clarity_grade: DF.Literal["FL", "IF", "VVS1", "VVS2", "VS1", "VS2", "SI1", "SI2", "I1", "I2", "I3"]
		color_grade: DF.Literal["D", "E", "F", "G", "H", "I", "J", "K", "L", "M"]
		diamond_budget: DF.Float
		diamond_detail: DF.Data | None
		jewelry_budget: DF.Float
		material: DF.Literal["", "18K", "14K"]
		note: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		product_type: DF.Data | None
		shape: DF.Literal["", "Round", "Princess", "Asscher", "Emerald", "Marquise", "Oval", "Radiant", "Pear", "Heart", "Cushion", "Baguette"]
		size: DF.Float
	# end: auto-generated types

	def before_save(self):
		self.set_diamond_detail()
		
	def set_diamond_detail(self):
		parts = []
		if self.size:
			parts.append(f"{self.size}")
		if self.shape:
			parts.append(self.shape)
		if self.color_grade:
			parts.append(self.color_grade)
		if self.clarity_grade:
			parts.append(self.clarity_grade)
		
		self.diamond_detail = " - ".join(parts) if parts else ""
	pass
