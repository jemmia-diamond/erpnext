import frappe

def execute():
    try:
        frappe.db.sql("""
        UPDATE `tabLead`
        SET `phone` = NULL
        WHERE `phone` = '';
    """)
    except Exception:
        frappe.db.rollback()
        print("Failed to update phone for leads")
        return
    frappe.db.commit()