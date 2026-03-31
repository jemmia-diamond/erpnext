import frappe

groups = [
        "Unspecified",
        "NC Cưới",
        "NC Khiếu nại",
        "NC TMTĐ",
        "NC Cầu hôn",
        "NC Tặng",
        "NC Bản thân",
        "NC trên 6.3 Ly",
        "NC Mã cạnh đẹp",
    ]

def execute():
    create_groups(groups)

def create_groups(groups_data):
    for data in groups_data:
        create_group(data)

def create_group(data):
    existing_name = frappe.db.get_value("Lead Demand", {"demand_label": data}, "name")
    if existing_name:
        print(f"{data} exists")
        return frappe.get_doc("Lead Demand", existing_name)

    doc_data = {
        "doctype": "Lead Demand",
        "demand_label": data,
    }

    group = frappe.get_doc(doc_data)
    group.insert()
    group.reload()
    print(f"Created {group.get("name")} {group.get("demand_label")}")
    return group
