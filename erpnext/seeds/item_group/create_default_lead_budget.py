import frappe

groups = [
        "Unspecified",
        "dưới 15 TRIỆU",
        "15-30 TRIỆU",
        "30-50 TRIỆU",
        "50-80 TRIỆU",
        "80-120 TRIỆU",
        "120-200 TRIỆU",
        "200-300 TRIỆU",
        "300-500 TRIỆU",
        "500-800 TRIỆU",
        "800 TRIỆU - 1 TỶ",
        "trên 1 TỶ"
    ]

def execute():
    create_groups(groups)

def create_groups(groups_data):
    for data in groups_data:
        create_group(data)

def create_group(data):
    existing_name = frappe.db.get_value("Lead Budget", {"budget_label": data}, "name")
    if existing_name:
        print(f"{data} exists")
        return frappe.get_doc("Lead Budget", existing_name)

    doc_data = {
        "doctype": "Lead Budget",
        "budget_label": data,
    }

    group = frappe.get_doc(doc_data)
    group.insert()
    group.reload()
    print(f"Created {group.get("name")} {group.get("budget_label")}")
    return group
