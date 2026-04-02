# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PaymentEntryReference(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		account: DF.Link | None
		account_type: DF.Data | None
		advance_voucher_no: DF.DynamicLink | None
		advance_voucher_type: DF.Link | None
		allocated_amount: DF.Float
		balance: DF.Currency
		bank: DF.Data | None
		bank_account: DF.Link | None
		bank_account_branch: DF.Data | None
		bank_account_no: DF.Data | None
		bill_no: DF.Data | None
		due_date: DF.Date | None
		exchange_gain_loss: DF.Currency
		exchange_rate: DF.Float
		gateway: DF.Data | None
		mode_of_payment: DF.Link | None
		order_number: DF.Data | None
		outstanding_amount: DF.Float
		paid_amount: DF.Currency
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		payment_date: DF.Datetime | None
		payment_order_status: DF.Data | None
		payment_request: DF.Link | None
		payment_term: DF.Link | None
		payment_term_outstanding: DF.Float
		payment_type: DF.Data | None
		reconcile_effect_on: DF.Date | None
		ref_order_date: DF.Date | None
		ref_order_number: DF.Data | None
		reference_doctype: DF.Link
		reference_name: DF.DynamicLink
		split_order_group_name: DF.Data | None
		total_amount: DF.Float
	# end: auto-generated types

	@property
	def payment_request_outstanding(self):
		if not self.payment_request:
			return

		return frappe.db.get_value("Payment Request", self.payment_request, "outstanding_amount")
