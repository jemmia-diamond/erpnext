import frappe


def execute():
    try: 
        frappe.db.sql("""
            UPDATE `tabLead`
            SET qualification_status = 'Qualified', qualified_by = 'Administrator'
            WHERE qualified_lead_date IS NOT NULL
            """)
    except Exception:
        frappe.db.rollback()
        print("Failed to update qualified lead date")
        return
    frappe.db.commit()
    