import frappe
class BaseConfig: 
    """
    Load environment variable
    """
    AI_HUB_URL : str=  frappe.conf.get("ai_hub_url")
    AI_HUB_ACCESS_TOKEN : str = frappe.conf.get("ai_hub_access_token")  
    AI_HUB_WEBHOOK : str = frappe.conf.get("ai_hub_webhook")
    DEFAULT_MAIL_OWNER : str = frappe.conf.get("default_mail_lead_owner")
    
config = BaseConfig()
