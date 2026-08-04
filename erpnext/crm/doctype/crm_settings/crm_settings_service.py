# Copyright (c) 2026, Jemmia and contributors
# For license information, please see license.txt

import frappe

CACHE_KEY = "crm_settings_dict"


def get_crm_settings():
	"""Get cached CRM Settings document dictionary from Redis cache."""
	settings = frappe.cache().get_value(CACHE_KEY)
	if settings is None:
		settings = frappe.db.get_singles_dict("CRM Settings")
		frappe.cache().set_value(CACHE_KEY, settings)
	return settings


def clear_crm_settings_cache():
	"""Clear cached CRM Settings and immediately update Redis cache with fresh settings."""
	frappe.cache().delete_value(CACHE_KEY)
	settings = frappe.db.get_singles_dict("CRM Settings")
	frappe.cache().set_value(CACHE_KEY, settings)
	return settings
