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

		clarity_grade: DF.Literal["", "FL", "IF", "VVS1", "VVS2", "VS1", "VS2", "SI1", "SI2", "SI3", "I1", "I2", "I3", "NA"]
		color_grade: DF.Literal["", "D (Kh\u00f4ng M\u00e0u)", "E (Kh\u00f4ng M\u00e0u)", "F (Kh\u00f4ng M\u00e0u)", "G (G\u1ea7n Nh\u01b0 Kh\u00f4ng M\u00e0u)", "H (G\u1ea7n Nh\u01b0 Kh\u00f4ng M\u00e0u)", "I (G\u1ea7n Nh\u01b0 Kh\u00f4ng M\u00e0u)", "J (G\u1ea7n Nh\u01b0 Kh\u00f4ng M\u00e0u)", "K (H\u01a1i V\u00e0ng)", "L (H\u01a1i V\u00e0ng)", "M (H\u01a1i V\u00e0ng)", "N (V\u00e0ng Nh\u1ea1t)", "O (V\u00e0ng Nh\u1ea1t)", "P (V\u00e0ng Nh\u1ea1t)", "Q (V\u00e0ng Nh\u1ea1t)", "R (V\u00e0ng Nh\u1ea1t)", "S (V\u00e0ng)", "T (V\u00e0ng)", "U (V\u00e0ng)", "V (V\u00e0ng)", "W (V\u00e0ng)", "X (V\u00e0ng)", "Y (V\u00e0ng)", "Z (V\u00e0ng)", "D, E, F", "G, H, I, J", "T\u1eeb K \u0111\u1ebfn Z", "Yellow (V\u00e0ng)", "Pink (H\u1ed3ng)", "Green (Xanh l\u00e1)", "Blue (Xanh d\u01b0\u01a1ng)", "Kh\u00f4ng ph\u00e2n lo\u1ea1i", "Black (M\u00e0u \u0110en)", "Grey (M\u00e0u X\u00e1m)", "Red (M\u00e0u \u0110\u1ecf)"]
		diamond_budget: DF.Float
		diamond_detail: DF.Data | None
		jewelry_budget: DF.Float
		material: DF.Literal["", "V\u00e0ng 18K", "V\u00e0ng 14K", "Platinum", "B\u1ea1c 925", "Kh\u00e1c"]
		note: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		product_type: DF.Data | None
		shape: DF.Literal["", "Round", "Princess", "Asscher", "Emerald", "Marquise", "Oval", "Radiant", "Pear", "Heart", "Cushion", "Baguette"]
		size: DF.Literal["", "3.6", "3.7", "3.8", "3.9", "4.0", "4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9", "5.0", "5.1", "5.2", "5.3", "5.4", "5.5", "5.6", "5.7", "5.8", "5.9", "6.0", "6.1", "6.2", "6.3", "6.4", "6.5", "6.6", "6.7", "6.8", "6.9", "7.0", "7.1", "7.2", "7.3", "7.4", "7.5", "7.6", "7.7", "7.8", "7.9", "8.0", "8.1", "8.2", "8.3", "8.4", "8.5", "8.6", "8.7", "8.8", "8.9", "9.0", "9.1", "9.2", "9.3", "9.4", "9.5", "9.6", "9.7", "9.8", "9.9", "10.0", "10.1", "10.2", "10.3", "10.4", "10.5", "10.6", "10.7", "10.8", "10.9", "11.0", "11.1", "11.2", "11.3", "11.4", "11.5", "11.6", "11.7", "11.8", "11.9", "12.0", "12.1", "12.2", "12.3", "12.4", "12.5", "12.6", "12.7", "12.8", "12.9", "13.0"]
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
