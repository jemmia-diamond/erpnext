from urllib.parse import quote

import frappe
import requests

from erpnext.config.config import config
from erpnext.utilities.phone_utils import get_phone_variants, normalize_to_standard_format


class CustomerService:
	@staticmethod
	@frappe.whitelist()
	def create_haravan_customer(customer_name):
		raw_phone = ""
		normalized_phone = ""
		try:
			customer = frappe.get_doc("Customer", customer_name)

			if customer.haravan_id:
				return {"status": "skipped", "message": "Haravan ID already exists"}

			haravan_token = config.HARAVAN_TOKEN
			if not haravan_token:
				raise ValueError("Haravan Token not found in site config.")

			first_name = ""
			last_name = ""
			if customer.customer_name:
				parts = customer.customer_name.strip().split(" ")
				if len(parts) > 1:
					first_name = parts[-1]
					last_name = " ".join(parts[:-1])
				else:
					first_name = parts[0]
					last_name = ""

			raw_phone = customer.mobile_no or customer.phone or ""
			normalized_phone = normalize_to_standard_format(raw_phone) if raw_phone else ""
			formatted_phone = f"00{normalized_phone}" if normalized_phone else ""

			gender_map = {"Female": 0, "Male": 1, "LGBT": 2}
			gender_val = gender_map.get(customer.gender, 2)

			payload = {
				"customer": {
					"first_name": first_name,
					"last_name": last_name,
					"email": customer.email_id or "",
					"phone": formatted_phone,
					"gender": gender_val,
				}
			}

			headers = {
				"Authorization": f"Bearer {haravan_token}",
				"Content-Type": "application/json",
				"Accept": "application/json",
			}

			response = requests.post(
				"https://apis.haravan.com/com/customers.json", json=payload, headers=headers
			)

			if response.status_code == 201:
				data = response.json()
				haravan_id = str(data.get("customer", {}).get("id", ""))
				if haravan_id:
					CustomerService.update_haravan_ids(customer, haravan_id)
				return {"status": "success", "haravan_id": haravan_id}

			elif response.status_code == 422:
				error_msg = str(response.json().get("errors", ""))
				if "đã được sử dụng" in error_msg:
					variants = get_phone_variants(raw_phone)
					for variant in variants:
						encoded_query = quote(f"phone:{variant}")
						search_url = (
							f"https://apis.haravan.com/com/customers/search.json?query={encoded_query}"
						)

						search_resp = requests.get(search_url, headers=headers)
						if search_resp.status_code == 200:
							search_data = search_resp.json()
							customers = search_data.get("customers", [])
							if customers:
								haravan_id = str(customers[0].get("id", ""))
								CustomerService.update_haravan_ids(customer, haravan_id)
								return {
									"status": "success",
									"message": "Linked existing customer",
									"haravan_id": haravan_id,
								}

				raise ValueError(f"Haravan Validation Error: {error_msg}")
			else:
				raise ValueError(f"Haravan API Error {response.status_code}: {response.text}")

		except Exception:
			frappe.log_error(title="Haravan Customer Creation Error", message=frappe.get_traceback())
			return {"status": "error", "message": "Error when create HRV customer"}

	@staticmethod
	def update_haravan_ids(customer, haravan_id):
		frappe.db.set_value("Customer", customer.name, "haravan_id", haravan_id)
		if customer.customer_primary_contact:
			contact = frappe.get_doc("Contact", customer.customer_primary_contact)
			contact.haravan_customer_id = haravan_id
			contact.first_name = customer.customer_name

			if contact.phone_nos:
				primary_phone_set = any(row.is_primary_phone for row in contact.phone_nos)
				if not primary_phone_set:
					contact.phone_nos[0].is_primary_phone = 1

			contact.save(ignore_permissions=True)
			frappe.db.commit()


@frappe.whitelist()
def create_haravan_customer_job(customer_name):
	CustomerService.create_haravan_customer(customer_name)
