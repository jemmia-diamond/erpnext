import frappe

groups = [
    {
        "channel": "google",
        "page_id": "",
        "source_name": "GG - Mail CSKH"   
    },
    {
        "channel": "call-center",
        "page_id": "",
        "source_name": "Call Center StringX"   
    },
    {
        "channel": "google",
        "page_id": "",
        "source_name": "GG - Form Website Jemmia.vn"   
    },
    {
        "channel": "Zalo",
        "page_id": "pzl_414930725736878626",
        "source_name": "ZNS - Jemmia Kiệt Hột Xoàn"   
    },
    {
        "channel": "Zalo",
        "page_id": "pzl_488577139896879905",
        "source_name": "ZNS - Jemmia Kiệt Hột Xoàn"   
    },
    {
        "channel": "Zalo",
        "page_id": "pzl_779852793569717677",
        "source_name": "ZNS - Jemmia Anh Kim Cương"   
    },
    {
        "channel": "Zalo",
        "page_id": "pzl_833581016608002860",
        "source_name": "ZNS - Jemmia Quý Tử Hột Xoàn"   
    },
    {
        "channel": "Zalo",
        "page_id": "zl_2838947343790196672",
        "source_name": "ZNS - Jemmia Diamond"   
    },
    {
        "channel": "Tiktok",
        "page_id": "ttm_-000vx1i3_6f-dgNlrIKPJp43a-FtDGPhp9V",
        "source_name": "TT - Bà Cô GIA"   
    },
    {
        "channel": "Tiktok",
        "page_id": "ttm_-0007ieZf-fCJ0OCOWwCHv3oEFiuNv8ZfCG3",
        "source_name": "TT - Quý Tử Hột Xoàn"   
    },
    {
        "channel": "Facebook",
        "page_id": "110263770893806",
        "source_name": "FB - Jemmia Diamond"   
    },
    {
        "channel": "Facebook",
        "page_id": "446215881902615",
        "source_name": "FB - Quý Tử Hột Xoàn"   
    },
    {
        "channel": "Facebook",
        "page_id": "434826109715125",
        "source_name": "FB - Anh Kim Cương"   
    },
    {
        "channel": "Facebook",
        "page_id": "114459901519364",
        "source_name": "FB - Kiệt Hột Xoàn"   
    },
    {
        "channel": "Facebook",
        "page_id": "104886481441594",
        "source_name": "FB - Jemmia Diamond - Hà Nội"   
    },
    {
        "channel": "Facebook",
        "page_id": "1743950302490722",
        "source_name": "FB - Jemmia Love Jewelry"   
    },
    {
        "channel": "Instagram",
        "page_id": "igo_17841405444769058",
        "source_name": "IG - Jemmia Love Jewelry"   
    },
    {
        "channel": "Instagram",
        "page_id": "igo_17841417742497903",
        "source_name": "IG - Jemmia Diamond"   
    },
    {
        "channel": "Tiktok",
        "page_id": "ttm_-000GnI37aFDBuqWw6N750AvvJXaodrxaoS6",
        "source_name": "TT - Jemmia Hột Xoàn"   
    },  
    {
        "channel": "Tiktok",
        "page_id": "ttm_-0001D42q_CH-ycWH7QLxlU-_NckyO8Xaz1C",
        "source_name": "TT - Anh Kim Cương"   
    },  
]

def execute():
    create_groups(groups)

def create_groups(groups_data):
    for data in groups_data:
        create_group(data)

def create_group(data):
    existing_name = frappe.db.get_value("Lead Source", {"source_name": data["source_name"], "pancake_page_id": data["page_id"], "pancake_platform": data["channel"]}, "name")
    if existing_name:
        print(f"{data['source_name']} exists")
        return frappe.get_doc("Lead Source", existing_name)

    doc_data = {
        "doctype": "Lead Source",
        "source_name": data["source_name"],
        "pancake_page_id": data["page_id"],
        "pancake_platform": data["channel"]
    }

    group = frappe.get_doc(doc_data)
    group.insert()
    group.reload()
    print(f"Created {group.get("name")} {group.get("source_name")}")
    return group
