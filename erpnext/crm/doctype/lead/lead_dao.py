import frappe

def get_lead_name_by_conversation_id(conversation_id: str):
	query = """
    SELECT tdl.link_name
    FROM tabContact tc
    JOIN `tabDynamic Link` tdl
        ON tc.name = tdl.parent
        AND tdl.parenttype = 'Contact'
    WHERE tc.pancake_conversation_id = %s
	"""
	result = frappe.db.sql(query, (conversation_id), as_dict=True)

	if len(result) > 0:
		link_name = result[0].link_name
		return link_name
	return None

def get_lead_by_name(lead_name: str):

    lead= None
    try:
        lead = frappe.get_doc("Lead", {
            "name" : lead_name
        })
    except Exception:
        return None

    return lead
