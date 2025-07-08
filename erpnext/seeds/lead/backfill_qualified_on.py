import frappe


def execute():
    try: 
        frappe.db.sql("""
            UPDATE `tabLead`
            SET qualified_on = qualified_lead_date
            """)
    except Exception:
        frappe.db.rollback()
        print("Failed to update qualified lead date")
        return
    frappe.db.commit()