import frappe


def execute():
    try: 
        frappe.db.sql("""
            UPDATE `tabLead`
            SET qualified_lead_date = DATE_SUB(qualified_lead_date, INTERVAL 7 HOUR)
            WHERE name <= 'CRM-LEAD-2025-0010758';
            """)
    except Exception:
        frappe.db.rollback()
        print("Failed to update qualified lead date")
        return
    frappe.db.commit()