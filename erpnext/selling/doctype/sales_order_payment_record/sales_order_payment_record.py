# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class SalesOrderPaymentRecord(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		date: DF.Date | None
		gateway: DF.Data | None
		kind: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		transaction_id: DF.Int
	# end: auto-generated types
	pass
