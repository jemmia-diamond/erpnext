# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import strip
import requests


class CouponCode(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amended_from: DF.Link | None
		cashback_ref_amount: DF.Currency
		coupon_name: DF.Data
		coupon_status: DF.Literal["Used", "Not Used"]
		coupon_type: DF.Literal["Invite", "Partner"]
		customer: DF.Link
		description: DF.TextEditor | None
		haravan_coupon_id: DF.Data | None
		maximum_use: DF.Int
		order_status: DF.Literal["Pending", "Paid"]
		total_price_amount: DF.Currency
		used: DF.Int
		user_name: DF.Data | None
		valid_from: DF.Date | None
		valid_upto: DF.Date | None
	# end: auto-generated types

	def validate(self):
		if self.coupon_type == "Partner":
			self.maximum_use = 1
			if not self.customer:
				frappe.throw(_("Please select the customer."))

	def autoname(self):
		self.coupon_name = strip(self.coupon_name)
		self.name = self.coupon_name

		if not self.coupon_code:
			if self.coupon_type == "Invite":
				self.coupon_code = "".join(i for i in self.coupon_name if not i.isdigit())[0:8].upper()
			elif self.coupon_type == "Partner":
				self.coupon_code = frappe.generate_hash()[:10].upper()


def update_all_customers_coupon_code():
	try:
		payload = {}
		response = requests.get("https://priority-api.jemmia.vn/coupon-ref/get-all", json=payload)

		if response.status_code != 200:
			frappe.throw("Failed to fetch data from priority API")

		results = response.json()
		for result in results:
			haravan_id = result.get("haravanId")
			owner_name = result.get("ownerName")
			haravan_coupon_code = result.get("couponHaravanCode")
			haravan_coupon_id = result.get("couponHaravanId")
			total_price = result.get("totalPrice", 0)
			used_by_name = result.get("usedByName") or ""
			cashback_ref = result.get("cashBackRef", 0)
			order_status = result.get("paymentStatus", "").capitalize() 
			coupon_status = result.get("couponStatus", "Used")
			coupon_type = result.get("couponType", "Invite")

			if not haravan_id or not owner_name or not haravan_coupon_code:
				continue

			customer = frappe.get_value("Customer", {"haravan_id": haravan_id}, "name")
			if not customer:
				continue

			coupon_name = frappe.get_value("Coupon Code", {"name": haravan_coupon_code}, "name")
			if coupon_name:
				continue
			coupon_code_name = frappe.get_value("Coupon Code", {"haravan_coupon_id": haravan_coupon_code}, "name")

			if not coupon_code_name:
				coupon_code = frappe.new_doc("Coupon Code")
			else:
				coupon_code = frappe.get_doc("Coupon Code", coupon_code_name)

			# Set common fields
			coupon_code.haravan_coupon_id = haravan_coupon_id
			coupon_code.coupon_name = haravan_coupon_code
			coupon_code.customer = customer
			coupon_code.user_name = used_by_name
			coupon_code.coupon_type = coupon_type
			coupon_code.total_price_amount = total_price
			coupon_code.cashback_ref_amount = cashback_ref
			coupon_code.order_status = order_status  # Must be 'Pending' or 'Paid'
			coupon_code.coupon_status = coupon_status  # Must be 'Used' or 'Not Used'

			if not coupon_code_name:
				coupon_code.insert()
			else:
				coupon_code.save()

			frappe.db.commit()
			frappe.msgprint(_("Updated coupon code for customer {0}").format(customer))

		frappe.msgprint(_("All coupon codes have been updated successfully."))

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Error updating coupon codes")
		frappe.db.rollback()
		frappe.throw(_("An error occurred while updating coupon codes: {0}").format(str(e)))
