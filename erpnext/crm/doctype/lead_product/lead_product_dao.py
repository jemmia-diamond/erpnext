import frappe 

def get_products_in_names(product_names):

	products = frappe.get_all(
		"Lead Product", 
		filters={"product_type": ["in", product_names]},
		fields = ["name", "product_type"]
	)
	
	return products

def get_lead_product(product_type):
    try:
        return frappe.get_doc(
			"Lead Product", {
				"product_type": product_type
			}
		)
    except Exception as e:
        return None

def create_lead_product(product_type):
	try:
		# Single DB query to fetch all 3 CRM Settings fields
		enabled, not_allowed_raw, allowed_raw = frappe.db.get_value(
			"CRM Settings",
			"CRM Settings",
			["allow_auto_create_lead_product", "not_allowed_product_types", "allowed_product_types"]
		) or (1, None, None)

		if not enabled:
			return None

		target_product = product_type.strip()

		# 1. Check NOT allowed list
		if not_allowed_raw:
			not_allowed_types = [item.strip() for item in not_allowed_raw.split(",") if item.strip()]
			if target_product in not_allowed_types:
				return None

		# 2. Check allowed list
		if allowed_raw:
			allowed_types = [item.strip() for item in allowed_raw.split(",") if item.strip()]
			if allowed_types and target_product not in allowed_types:
				return None

		new_lead_product = frappe.new_doc("Lead Product")
		new_lead_product.update({
			"product_type": product_type
		})
		return new_lead_product.save()
	except Exception as e:
		return None
