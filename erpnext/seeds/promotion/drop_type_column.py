import frappe

def execute():
    try:
        frappe.db.sql("ALTER TABLE `tabPromotion` DROP `type`")
        frappe.db.commit()
    except:
        frappe.db.rollback()
