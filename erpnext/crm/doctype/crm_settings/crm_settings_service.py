# Copyright (c) 2026, Jemmia and contributors
# For license information, please see license.txt

import frappe

CACHE_KEY = "crm_settings_dict"


def _cast_settings(settings):
	if not settings:
		return {}
	casted = dict(settings)
	for key, val in casted.items():
		if isinstance(val, str):
			val_str = val.strip()
			if val_str.isdigit() or (val_str.startswith("-") and val_str[1:].isdigit()):
				casted[key] = frappe.utils.cint(val_str)
			elif val_str.startswith(("[", "{")):
				try:
					parsed = frappe.parse_json(val_str)
					if parsed is not None:
						casted[key] = parsed
				except Exception:
					pass
	return casted


@frappe.whitelist()
def get_crm_settings():
	"""Get cached CRM Settings document dictionary from Redis cache."""
	settings = frappe.cache().get_value(CACHE_KEY)
	if settings is None:
		raw = frappe.db.get_singles_dict("CRM Settings")
		settings = _cast_settings(raw)
		frappe.cache().set_value(CACHE_KEY, settings)
	return settings


def clear_crm_settings_cache():
	"""Clear cached CRM Settings and immediately update Redis cache with fresh settings."""
	frappe.cache().delete_value(CACHE_KEY)
	raw = frappe.db.get_singles_dict("CRM Settings")
	settings = _cast_settings(raw)
	frappe.cache().set_value(CACHE_KEY, settings)
	return settings
