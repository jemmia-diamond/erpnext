import frappe

class ConfigBase:
    GAPONE_API_KEY: str  = frappe.conf.get("gapone_api_key")

config = ConfigBase()