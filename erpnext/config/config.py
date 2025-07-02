import frappe
class BaseConfig: 
    """
    Load environment variable
    """
    DEFAULT_MAIL_OWNER : str = frappe.conf.get("default_mail_lead_owner")
    DATE_ASSIGN_LEAD_OWNER : str = "2025-06-15T14:00:00+00:00"
    STRINGEE_API_KEY_SID: str = frappe.conf.get("stringee_api_key_sid")
    STRINGEE_API_KEY_SECRET: str = frappe.conf.get("stringee_api_key_secret")
config = BaseConfig()
