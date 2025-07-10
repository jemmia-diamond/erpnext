import frappe

def map_customer_lead():
    frappe.db.sql("""
        UPDATE tabCustomer c
        	JOIN `tabDynamic Link` dl ON dl.link_doctype = 'Customer' AND dl.link_name = c.name
        	JOIN tabContact co ON dl.parent = co.name
        	JOIN tabLead l ON co.phone = l.phone
        SET c.lead_name = l.name
        WHERE c.lead_name IS NULL;
    """)
    frappe.db.commit()