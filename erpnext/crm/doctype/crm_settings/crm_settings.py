# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.model.document import Document
from erpnext.crm.doctype.crm_settings.crm_settings_service import clear_crm_settings_cache
from erpnext.crm.frappe_crm_api import is_crm_installed
from erpnext.crm.doctype.frappe_crm_allowed_user.frappe_crm_allowed_user import FrappeCRMAllowedUser

class CRMSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		allow_auto_create_lead_product: DF.Check
		allow_lead_duplication_based_on_emails: DF.Check
		allow_subsequent_auto_opportunity: DF.Check
		allowed_product_types: DF.Text | None
		auto_close_opportunity: DF.Check
		auto_create_opportunity: DF.Check
		auto_create_opportunity_on_converted_lead: DF.Check
		allowed_users: DF.TableMultiSelect[FrappeCRMAllowedUser]
		auto_creation_of_contact: DF.Check
		auto_nurture_leads: DF.Check
		auto_opportunity_mandatory_fields: DF.Text | None
		campaign_naming_by: DF.Literal["Campaign Name", "Naming Series"]
		carry_forward_communication_and_comments: DF.Check
		close_opportunity_after_days: DF.Int
		default_valid_till: DF.Data | None
		not_allowed_product_types: DF.Text | None
		opportunity_sync_field_mappings: DF.Code | None
		lost_reason_messages: DF.Code | None
		sync_lead_to_in_progress_opportunity: DF.Check
		sync_opportunity_date_from_old_lead_qualified_on: DF.Check
		transfer_assign_to_lead_owner: DF.Check
		enable_frappe_crm_data_synchronization: DF.Check
		enable_opportunity_creation_from_contact_us: DF.Check
		update_timestamp_on_new_communication: DF.Check
	# end: auto-generated types

	def on_update(self):
		clear_crm_settings_cache()

	def on_change(self):
		clear_crm_settings_cache()

	def validate(self):
		frappe.db.set_default("campaign_naming_by", self.get("campaign_naming_by", ""))
		self.validate_enable_opportunity_creation_from_contact_us()
		self.validate_allowed_users()

	def validate_enable_opportunity_creation_from_contact_us(self):
		contact_disabled = frappe.get_single_value("Contact Us Settings", "is_disabled")

		if self.enable_opportunity_creation_from_contact_us and contact_disabled:
			frappe.throw(
				_(
					"Cannot enable Opportunity creation from Contact Us because the Contact Us form is disabled."
				)
			)

	def validate_allowed_users(self):
		if self.enable_frappe_crm_data_synchronization and not (is_crm_installed() or self.allowed_users):
			frappe.throw(
				_(
					"Please add atleast one user on Allowed Users to allow Data Synchronization from Frappe CRM site."
				)
			)

		if self.enable_frappe_crm_data_synchronization and is_crm_installed() and self.allowed_users:
			frappe.throw(_("Allowed Users is not required as Frappe CRM is already installed on the site."))

	def before_save(self):
		self.clear_allowed_users()

	def on_update(self):
		self.custom_fields_for_frappe_crm_data_sync()

	def clear_allowed_users(self):
		if not self.enable_frappe_crm_data_synchronization:
			self.allowed_users = []

	def custom_fields_for_frappe_crm_data_sync(self):
		custom_fields = {
			"Quotation": [
				{
					"fieldname": "crm_deal",
					"fieldtype": "Data",
					"label": "Frappe CRM Deal",
					"insert_after": "party_name",
				}
			],
			"Customer": [
				{
					"fieldname": "crm_deal",
					"fieldtype": "Data",
					"label": "Frappe CRM Deal",
					"insert_after": "prospect_name",
				}
			],
		}

		create_custom_fields(custom_fields, ignore_validate=True)
