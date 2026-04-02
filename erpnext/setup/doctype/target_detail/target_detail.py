# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


from frappe.model.document import Document


class TargetDetail(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		distribution_id: DF.Link
		fiscal_year: DF.Link
		item_group: DF.Link | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		target_amount: DF.Float
		target_lead_received: DF.Int
		target_previous_month_qualified: DF.Int
		target_qty: DF.Float
		target_qualified_leads: DF.Int
		target_qualified_to_orders: DF.Int
	# end: auto-generated types

	pass
