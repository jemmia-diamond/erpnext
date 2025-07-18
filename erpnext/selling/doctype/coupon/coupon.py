import frappe
import requests
from frappe import _
from frappe.utils import flt
from frappe.model.document import Document

class Coupon(Document):
	# begin: auto-generated types
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
	# end: auto-generated types

def update_all_customers_coupon_code():
	try:
		response = requests.get("https://priority-api.jemmia.vn/coupon-ref/get-all", json={})

		if response.status_code != 200:
			frappe.throw(_("Failed to fetch data from priority API"))

		results = response.json()
		updated_count = 0
		skipped_count = 0

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
				skipped_count += 1
				continue

			customer = frappe.get_value("Customer", {"haravan_id": haravan_id}, "name")
			if not customer:
				frappe.logger().info(f"Skipped: Customer with haravan_id {haravan_id} not found.")
				skipped_count += 1
				continue

			# Check if already exists by name
			existing_coupon_by_name = frappe.get_value("Coupon", {"haravan_coupon_id": haravan_coupon_id}, "name")
			if existing_coupon_by_name:
				skipped_count += 1
				continue

			# Check by haravan_coupon_id
			existing_coupon = frappe.get_value("Coupon", {"coupon_name": haravan_coupon_code}, "name")

			if existing_coupon:
				coupon_doc = frappe.get_doc("Coupon", existing_coupon)
			else:
				coupon_doc = frappe.new_doc("Coupon")

			# Set fields (must match field names in Doctype)
			coupon_doc.haravan_coupon_id = haravan_coupon_id
			coupon_doc.coupon_name = haravan_coupon_code
			coupon_doc.customer = customer
			coupon_doc.user = used_by_name  # fieldname is 'user' per your type hints
			coupon_doc.coupon_type = coupon_type
			coupon_doc.total_price = total_price
			coupon_doc.cashback_ref = cashback_ref
			coupon_doc.payment_status = payment_status  # fieldname is 'payment_status'
			# Optional: if you have a custom field 'coupon_status', you must add it to type hints too

			if not existing_coupon:
				coupon_doc.insert(ignore_permissions=True)
			else:
				coupon_doc.save(ignore_permissions=True)

			updated_count += 1

		frappe.db.commit()
		frappe.msgprint(_("{0} coupon codes updated, {1} skipped.").format(updated_count, skipped_count))

	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Error updating coupon codes")
		frappe.throw(_("An error occurred while updating coupon codes: {0}").format(str(e)))
