import frappe

def get_lead_name_by_conversation_id(conversation_id: str):
	contact_name = frappe.db.get_value(
		"Contact",
		{"pancake_conversation_id": conversation_id},
		"name",
	)
	if not contact_name:
		return None
	link_name = frappe.db.get_value(
		"Dynamic Link",
		{
			"parent": contact_name,
			"parenttype": "Contact",
			"link_doctype": "Lead",
		},
		"link_name",
	)
	return link_name

def get_lead_by_name(lead_name: str):

    lead= None
    try:
        lead = frappe.get_doc("Lead", {
            "name" : lead_name
        })
    except Exception:
        return None

    return lead
