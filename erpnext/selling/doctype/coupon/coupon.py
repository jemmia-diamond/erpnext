import frappe
import requests
from frappe import _
from frappe.utils import flt
from frappe.model.document import Document
from erpnext.config.config import config

class Coupon(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		cashback_ref: DF.Data | None
		coupon_name: DF.Data
		coupon_type: DF.Literal["Invite", "Partner"]
		customer: DF.Link
		haravan_coupon_id: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		payment_status: DF.Literal["Paid", "Pending"]
		total_price: DF.Currency
		user: DF.Data | None
	# end: auto-generated types
	from typing import TYPE_CHECKING
	if TYPE_CHECKING:
		from frappe.types import DF

		cashback_ref: DF.Data | None
		coupon_name: DF.Data
		coupon_type: DF.Literal["Invite", "Partner"]
		customer: DF.Link
		haravan_coupon_id: DF.Data | None
		payment_status: DF.Literal["Paid", "Pending"]
		total_price: DF.Currency
		user: DF.Data | None

def update_all_customers_coupon_code():
	try:
		priority_bearer_token: str = config.PRIORITY_BEARER_TOKEN
		priority_base_url: str = config.PRIORITY_BASE_URL
		response = requests.get(f"{priority_base_url}/sync-crm/coupon-ref?updatedInCrm=true", json={}, headers={"Authorization": f"Bearer {priority_bearer_token}"})

		if response.status_code != 200:
			frappe.throw(_("Failed to fetch data from priority API"))

		results = response.json()

		for result in results:
			haravan_id = result.get("haravanId")
			owner_name = result.get("ownerName")
			haravan_coupon_code = result.get("couponHaravanCode")
			haravan_coupon_id = result.get("couponHaravanId")
			total_price = flt(result.get("totalPrice", 0))
			used_by_name = result.get("usedByName") or ""
			cashback_ref = flt(result.get("cashBackRef", 0))
			payment_status = result.get("paymentStatus", "Pending").capitalize()
			coupon_status = result.get("couponStatus", "Used")
			coupon_type = result.get("couponType", "Invite")

			if not haravan_id or not owner_name or not haravan_coupon_code:
				continue

			customer = frappe.get_value("Customer", {"haravan_id": haravan_id}, "name")
			if not customer:
				frappe.logger().info(f"Skipped: Customer with haravan_id {haravan_id} not found.")
				continue

			existing_coupon_by_name = frappe.get_value("Coupon", {"haravan_coupon_id": haravan_coupon_id}, "name")
			if existing_coupon_by_name:
				continue

			existing_coupon = frappe.get_value("Coupon", {"coupon_name": haravan_coupon_code}, "name")

			if existing_coupon:
				coupon_doc = frappe.get_doc("Coupon", existing_coupon)
			else:
				coupon_doc = frappe.new_doc("Coupon")

			coupon_doc.haravan_coupon_id = haravan_coupon_id
			coupon_doc.coupon_name = haravan_coupon_code
			coupon_doc.customer = customer
			coupon_doc.user = used_by_name  
			coupon_doc.coupon_type = coupon_type
			coupon_doc.total_price = total_price
			coupon_doc.cashback_ref = cashback_ref
			coupon_doc.payment_status = payment_status
			coupon_doc.parent = customer
			coupon_doc.parentfield = "coupon_table"
			coupon_doc.parenttype = "Customer"  
			
			if not existing_coupon:
				coupon_doc.insert(ignore_permissions=True)
			else:
				coupon_doc.save(ignore_permissions=True)

		frappe.db.commit()
		
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Error updating coupon codes")
		frappe.throw(_("An error occurred while updating coupon codes: {0}").format(str(e)))
