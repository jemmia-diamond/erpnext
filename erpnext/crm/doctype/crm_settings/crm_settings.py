# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from erpnext.crm.doctype.crm_settings.crm_settings_service import clear_crm_settings_cache

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
		update_timestamp_on_new_communication: DF.Check
	# end: auto-generated types

	def validate(self):
		frappe.db.set_default("campaign_naming_by", self.get("campaign_naming_by", ""))

	def on_update(self):
		clear_crm_settings_cache()

	def on_change(self):
		clear_crm_settings_cache()