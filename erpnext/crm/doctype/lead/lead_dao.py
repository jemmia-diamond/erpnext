import frappe
from erpnext.config.config import config

def get_leads_to_summary():
    # condition to summary pancake
	# pancake_conversation_id is not null and c.pancake_page_id is not null
	# last_message_customer exist  -> if null mean customer not replied
	# last_message_customer > last_migration  | last_migration is null
	# lead does not own opportunity -> lead has opportunity dont need to convert 
	
    sql=f"""
    SELECT
    c.pancake_conversation_id,
    c.pancake_page_id
    FROM
        tabContact c
    WHERE 
    c.pancake_conversation_id IS NOT NULL
    AND c.pancake_page_id IS NOT NULL
    AND c.last_message_time IS NOT NULL
    AND (c.last_summarize_time IS NULL
        OR c.last_message_time > c.last_summarize_time)
    AND c.name  NOT IN (
        SELECT
            tdl.parent
        FROM
            `tabDynamic Link` tdl
        WHERE
            tdl.link_name NOT IN (
                SELECT
                    tl.name
                FROM
                    tabLead tl
                WHERE
                    tl.name IN (
                        SELECT
                            tOp.party_name
                        FROM
                            tabOpportunity tOp
                        WHERE
                            tOp.opportunity_from = 'Lead'
                    )
                AND tl.first_reach_at < '{config.FIRST_REACH_AT_LIMIT_SUMMARY}'
            )
            AND tdl.parenttype = 'Contact'
    )
    GROUP BY
        c.pancake_conversation_id;
    """
    pancakes = frappe.db.sql(sql, as_dict=True)
    return pancakes

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
