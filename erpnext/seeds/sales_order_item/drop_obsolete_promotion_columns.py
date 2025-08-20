import frappe


def execute():
    try:
        frappe.db.sql("""
            ALTER TABLE `tabSales Order Item`
            DROP COLUMN g0,
            DROP COLUMN g1,
            DROP COLUMN g2,
            DROP COLUMN g3,
            DROP COLUMN g4,
            DROP COLUMN g5,
            DROP COLUMN g6,
            DROP COLUMN g7;
        """)
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        print("Failed to drop obsolete promotion columns")
        return