from copy import deepcopy
import frappe

DEFAULT_LEAD_DASHBOARD = {
	"fieldname": "lead",
	"non_standard_fieldnames": {
		"Quotation": "party_name",
		"Opportunity": "party_name",
		"Customer": "lead_name",
	},
	"dynamic_links": {
		"party_name": ["Lead", "quotation_to"],
	},
	"transactions": [
		{"items": ["Opportunity", "Quotation", "Prospect", "Customer"]},
	],
}


def get_data():
	data = deepcopy(DEFAULT_LEAD_DASHBOARD)
	try:
		crm_settings = frappe.get_cached_doc("CRM Settings")
		raw_config = crm_settings.get("lead_connections_config")
		if raw_config:
			custom = frappe.parse_json(raw_config) if isinstance(raw_config, str) else raw_config
			if isinstance(custom, list):
				data["transactions"] = custom
			elif isinstance(custom, dict):
				if custom.get("transactions"):
					data["transactions"] = custom["transactions"]
				if custom.get("non_standard_fieldnames"):
					data["non_standard_fieldnames"].update(custom["non_standard_fieldnames"])
				if custom.get("dynamic_links"):
					data["dynamic_links"].update(custom["dynamic_links"])
				if custom.get("fieldname"):
					data["fieldname"] = custom["fieldname"]
				if custom.get("internal_links"):
					data.setdefault("internal_links", {}).update(custom["internal_links"])
	except Exception:
		frappe.log_error(title="Failed to load Lead connections from CRM Settings")

	return data

