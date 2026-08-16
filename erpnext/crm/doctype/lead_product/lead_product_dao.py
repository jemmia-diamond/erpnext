import frappe

from erpnext.crm.doctype.crm_settings.crm_settings_service import get_crm_settings


def get_products_in_names(product_names):
	products = frappe.get_all(
		"Lead Product", filters={"product_type": ["in", product_names]}, fields=["name", "product_type"]
	)

	return products


def get_lead_product(product_type):
	try:
		return frappe.get_doc("Lead Product", {"product_type": product_type})
	except Exception:
		return None


def create_lead_product(product_type):
	try:
		crm_settings = get_crm_settings()
		enabled = crm_settings.get("allow_auto_create_lead_product", 1)
		if not enabled:
			return None

		target_product = product_type.strip()

		# 1. Check NOT allowed list
		not_allowed_raw = crm_settings.get("not_allowed_product_types")
		if not_allowed_raw:
			not_allowed_types = [item.strip() for item in not_allowed_raw.split(",") if item.strip()]
			if target_product in not_allowed_types:
				return None

		# 2. Check allowed list
		allowed_raw = crm_settings.get("allowed_product_types")
		if allowed_raw:
			allowed_types = [item.strip() for item in allowed_raw.split(",") if item.strip()]
			if allowed_types and target_product not in allowed_types:
				return None

		new_lead_product = frappe.new_doc("Lead Product")
		new_lead_product.update({"product_type": product_type})
		return new_lead_product.save()
	except Exception:
		return None
