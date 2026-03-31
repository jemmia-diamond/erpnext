import frappe 

def get_products_in_names(product_names):

	products = frappe.get_all(
		"Lead Product", 
		filters={"product_type": ["in", product_names]},
		fields = ["name", "product_type"]
	)
	
	return products