import frappe

def get_lead_name_by_conversation_id(conversation_id: str):
	names = frappe.get_all(
		"Contact",
		filters={"pancake_conversation_id": conversation_id},
		order_by="modified desc",
		pluck="name",
		limit=1,
	)
	if not names:
		return None
	try:
		dupe_count = frappe.db.count("Contact", {"pancake_conversation_id": conversation_id})
		if dupe_count and dupe_count > 1:
			frappe.logger().warning(
				f"Multiple Contacts ({dupe_count}) share pancake_conversation_id={conversation_id}; using most recent."
			)
	except Exception:
		pass
	contact_name = names[0]
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
