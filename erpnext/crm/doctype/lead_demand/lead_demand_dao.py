import frappe 

def get_lead_purpose(purpose: str):
	if not purpose:
		return None

	lead_purpose = None
	try:
		lead_purpose = frappe.get_doc("Lead Demand", {
			"demand_label": purpose
		})
	except Exception:
		return None
	
	return lead_purpose