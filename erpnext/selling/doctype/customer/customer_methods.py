import frappe

def map_customer_lead():
    try:
        frappe.db.sql("""
            UPDATE tabCustomer c
	            JOIN `tabDynamic Link` dl ON dl.link_doctype = 'Customer' AND dl.link_name = c.name
	            JOIN tabContact co ON dl.parent = co.name
	            JOIN tabLead l ON co.phone = l.phone AND LENGTH(l.phone) >= 10 AND LENGTH(co.phone) >= 10
            SET c.lead_name = l.name
            WHERE c.lead_name IS NULL;
        """)
    except Exception:
        frappe.db.rollback()
        return
    frappe.db.commit()
