import frappe

def execute():
    try:
        frappe.db.sql("""
            UPDATE tabLead tl
                JOIN tabProvince tp ON tl.province = tp.name
                JOIN tabRegion tr ON tp.region = tr.name
            SET tl.region = tr.name;
            """)
    except Exception:
        frappe.db.rollback()
        print("Failed to update region for leads")
        return
    frappe.db.commit()