import frappe
def find_range_budget(budget_from: int | None, budget_to:int | None):

	if budget_from is None and budget_to is None: 
		return None
	
	lead_budgets = None
	filters = {
	}
	if budget_to:
		filters["budget_to"] = [">=", budget_to]
	
	if budget_from:
		filters["budget_from"] = ["<=", budget_from]

	lead_budgets = frappe.get_all(
		"Lead Budget", 
		filters = filters, 
		limit_page_length=1, 
		fields=["name", "budget_label"],
		order_by="budget_to asc"
	)

	if len(lead_budgets) > 0:
		return lead_budgets[0]
	
	return None