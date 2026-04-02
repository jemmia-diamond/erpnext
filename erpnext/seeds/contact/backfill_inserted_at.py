import frappe


def execute():
    try: 
        frappe.db.sql("""
            UPDATE `tabContact`
            SET inserted_at = pancake_inserted_at;
            """)
    except Exception:
        frappe.db.rollback()
        print("Failed to update qualified lead date")
        return
    frappe.db.commit()