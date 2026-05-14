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

		# Collect unique customers from the delta response
		customers_to_update = set()
		for result in results:
			owner_haravan_id = result.get("haravanId")
			if owner_haravan_id:
				customers_to_update.add(owner_haravan_id)

		# For each unique customer, fetch their full coupon list and rebuild the child table
		# This ensures we don't duplicate rows or lose distinct sales orders.
		for haravan_id in customers_to_update:
			customer_name = frappe.get_value("Customer", {"haravan_id": haravan_id}, "name")
			if customer_name:
				update_customers_coupons(customer_name, haravan_id)

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

		customer_doc = frappe.get_doc("Customer", customer_name)

		# Clear existing child table to prevent deduplication/overwriting issues
		customer_doc.set("coupon_table", [])

		for result in customer_coupons:
			if not result.get("couponHaravanCode"):
				continue

			# Append every single object as a distinct new row
			coupon_row = customer_doc.append("coupon_table", {})
			_populate_coupon_row(coupon_row, result, customer_name)

		customer_doc.save(ignore_permissions=True)
		frappe.db.commit()

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), f"Error updating coupons for customer {customer_name}")
		return

def _populate_coupon_row(coupon_row, result, customer_name):
	"""Populate API response directly into the Coupon child table row"""
	haravan_coupon_id = result.get("couponHaravanId")
	user_haravan_id = result.get("userHaravanId")
	order_haravan_id = result.get("orderHaravanId")

	user = frappe.get_value("Customer", {"haravan_id": user_haravan_id}, "name") if user_haravan_id else None

	sales_order = None
	if order_haravan_id:
		sales_order = frappe.get_value("Sales Order", {"haravan_order_id": str(order_haravan_id)}, "name")

	coupon_row.haravan_coupon_id = haravan_coupon_id
	coupon_row.coupon_name = result.get("couponHaravanCode")
	coupon_row.user = user
	coupon_row.sales_order = sales_order
	coupon_row.coupon_type = result.get("couponType", "Invite")
	coupon_row.total_price = flt(result.get("totalPrice", 0))
	coupon_row.cashback_ref = flt(result.get("cashBackRef", 0))
	coupon_row.payment_status = result.get("paymentStatus").capitalize()

	if result.get("startDate"):
		dt = get_datetime(result.get("startDate"))
		coupon_row.start_date = dt.replace(tzinfo=None)

	if result.get("endDate"):
		dt = get_datetime(result.get("endDate"))
		coupon_row.end_date = dt.replace(tzinfo=None)
