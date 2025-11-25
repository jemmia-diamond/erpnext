import frappe
import requests
from frappe import _
from frappe.utils import flt
from frappe.model.document import Document
from erpnext.config.config import config
from frappe.utils import get_datetime

class Coupon(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		cashback_ref: DF.Currency
		coupon_name: DF.Data
		coupon_type: DF.Literal["Invite", "Partner"]
		customer: DF.Link
		haravan_coupon_id: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		payment_status: DF.Literal["Paid", "Pending"]
		total_price: DF.Currency
		user: DF.Link | None
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

		response = requests.get(
			f"{priority_base_url}/sync-crm/coupon-ref?updatedInCrm=false",
			json={},
			headers={"Authorization": f"Bearer {priority_bearer_token}"}
		)

		if response.status_code != 200:
			frappe.throw(_("Failed to fetch data from priority API"))

		results = response.json()

		for result in results:
			owner_haravan_id = result.get("haravanId")
			user_haravan_id = result.get("userHaravanId")
			haravan_coupon_code = result.get("couponHaravanCode")
			haravan_coupon_id = result.get("couponHaravanId")
			total_price = flt(result.get("totalPrice", 0))
			used_by_name = result.get("usedByName") or ""
			cashback_ref = flt(result.get("cashBackRef", 0))
			payment_status = result.get("paymentStatus", "Pending").capitalize()
			coupon_status = result.get("couponStatus", "Used")
			coupon_type = result.get("couponType", "Invite")

			if not owner_haravan_id or not haravan_coupon_code:
				continue

			customer = frappe.get_value("Customer", {"haravan_id": owner_haravan_id}, "name")
			if not customer:
				frappe.logger().info(f"Skipped: Customer with haravan_id {owner_haravan_id} not found.")
				continue

			user = frappe.get_value("Customer", {"haravan_id": user_haravan_id}, "name") if user_haravan_id else None

			existing_coupon = frappe.get_value("Coupon", {"haravan_coupon_id": haravan_coupon_id}, "name")

			if existing_coupon:
				coupon_doc = frappe.get_doc("Coupon", existing_coupon)
			else:
				coupon_doc = frappe.new_doc("Coupon")

			coupon_doc.haravan_coupon_id = haravan_coupon_id
			coupon_doc.coupon_name = haravan_coupon_code
			coupon_doc.customer = customer
			coupon_doc.user = user
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

@frappe.whitelist()
def update_customers_coupons(customer_name, customer_haravan_id):
	"""
	Update coupons for a specific customer by fetching from Priority API.

	Args:
		customer_name: ERPNext Customer name
		customer_haravan_id: Haravan ID of the customer
	"""
	try:
		priority_bearer_token: str = config.PRIORITY_BEARER_TOKEN
		priority_base_url: str = config.PRIORITY_BASE_URL
		response = requests.get(
			f"{priority_base_url}/sync-crm/coupon-ref?haravanId={customer_haravan_id}",
			json={},
			headers={"Authorization": f"Bearer {priority_bearer_token}"}
		)

		if response.status_code != 200:
			return

		customer_coupons = response.json()
		if not customer_coupons:
			return

		# Early return if coupon count matches
		# current_coupon_count = frappe.db.count("Coupon", {"customer": customer_name})
		# if len(customer_coupons) == current_coupon_count:
		# 	return

		for result in customer_coupons:
			if not result.get("couponHaravanCode"):
				continue

			coupon_doc, existing_coupon = _map_coupon_from_api(result, customer_name)

			if not existing_coupon:
				coupon_doc.insert(ignore_permissions=True)
			else:
				coupon_doc.save(ignore_permissions=True)

		frappe.db.commit()
		customer_doc = frappe.get_doc("Customer", customer_name)
		customer_doc.save(ignore_permissions=True)

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), f"Error updating coupons for customer {customer_name}")
		return

def _map_coupon_from_api(result, customer_name):
	"""Map API response to Coupon document fields"""
	haravan_coupon_id = result.get("couponHaravanId")
	user_haravan_id = result.get("userHaravanId")
	order_haravan_id = result.get("orderHaravanId")

	user = frappe.get_value("Customer", {"haravan_id": user_haravan_id}, "name") if user_haravan_id else None

	sales_order = None
	if order_haravan_id:
		sales_order = frappe.get_value("Sales Order", {"haravan_order_id": str(order_haravan_id)}, "name")

	existing_coupon = frappe.get_value("Coupon", {"haravan_coupon_id": haravan_coupon_id}, "name")

	if existing_coupon:
		coupon_doc = frappe.get_doc("Coupon", existing_coupon)
	else:
		coupon_doc = frappe.new_doc("Coupon")

	coupon_doc.haravan_coupon_id = haravan_coupon_id
	coupon_doc.coupon_name = result.get("couponHaravanCode")
	coupon_doc.customer = customer_name
	coupon_doc.user = user
	coupon_doc.sales_order = sales_order
	coupon_doc.coupon_type = result.get("couponType", "Invite")
	coupon_doc.total_price = flt(result.get("totalPrice", 0))
	coupon_doc.cashback_ref = flt(result.get("cashBackRef", 0))
	coupon_doc.payment_status = result.get("paymentStatus", "Pending").capitalize()

	if result.get("startDate"):
		dt = get_datetime(result.get("startDate"))
		coupon_doc.start_date = dt.replace(tzinfo=None)

	if result.get("endDate"):
		dt = get_datetime(result.get("endDate"))
		coupon_doc.end_date = dt.replace(tzinfo=None)

	coupon_doc.parent = customer_name
	coupon_doc.parentfield = "coupon_table"
	coupon_doc.parenttype = "Customer"

	return coupon_doc, existing_coupon
