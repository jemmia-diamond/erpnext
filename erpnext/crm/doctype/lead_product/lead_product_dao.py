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
		new_lead_product = frappe.new_doc("Lead Product")
		new_lead_product.update({
			"product_type": product_type
		})
		return new_lead_product.save()
	except Exception as e:
		return None
