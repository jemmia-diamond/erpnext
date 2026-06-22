# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
import json

import frappe
from frappe import _
from frappe.contacts.address_and_contact import (
	delete_contact_and_address,
	load_address_and_contact,
)
from frappe.contacts.doctype.address.address import get_default_address
from frappe.contacts.doctype.contact.contact import Contact, get_default_contact
from frappe.email.inbox import link_communication_to_document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import comma_and, get_link_to_form, has_gravatar, validate_email_address

from erpnext.accounts.party import set_taxes
from erpnext.config.config import config
from erpnext.controllers.selling_controller import SellingController
from erpnext.crm.utils import CRMNote, copy_comments, link_communications, link_open_events
from erpnext.selling.doctype.customer.customer import parse_full_name
from frappe.utils import date_diff, now_datetime


class Lead(SellingController, CRMNote):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from erpnext.crm.doctype.crm_note.crm_note import CRMNote
		from erpnext.crm.doctype.lead_product_item.lead_product_item import LeadProductItem
		from frappe.types import DF

		account_number: DF.Data | None
		address: DF.Data | None
		annual_revenue: DF.Currency
		bank_branch: DF.Literal[None]
		bank_district: DF.Literal[None]
		bank_name: DF.Link | None
		bank_province: DF.Literal[None]
		bank_ward: DF.Literal[None]
		birth_date: DF.Date | None
		blog_subscriber: DF.Check
		budget_lead: DF.Link | None
		ceo_name: DF.Data | None
		check_duplicate: DF.Link | None
		city: DF.Data | None
		company: DF.Link | None
		company_name: DF.Data | None
		country: DF.Link | None
		customer: DF.Link | None
		date_of_issuance: DF.Date | None
		disabled: DF.Check
		email_id: DF.Data | None
		expected_delivery_date: DF.Date | None
		fax: DF.Data | None
		first_channel: DF.Link | None
		first_name: DF.Data | None
		first_reach_at: DF.Datetime | None
		gender: DF.Link | None
		image: DF.AttachImage | None
		industry: DF.Link | None
		is_assigned: DF.Check
		job_title: DF.Data | None
		language: DF.Link | None
		last_name: DF.Data | None
		lead_name: DF.Data | None
		lead_owner: DF.Link | None
		lead_received_date: DF.Datetime | None
		lead_source_name: DF.Data | None
		lead_source_platform: DF.Data | None
		lead_stage: DF.Literal["Lead", "Qualified Lead", "Opportunity", "Customer"]
		market_segment: DF.Link | None
		middle_name: DF.Data | None
		mobile_no: DF.Data | None
		naming_series: DF.Literal["CRM-LEAD-.YYYY.-"]
		no_of_employees: DF.Literal["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]
		notes: DF.Table[CRMNote]
		pancake_data: DF.JSON | None
		personal_id: DF.Data | None
		personal_tax_id: DF.Data | None
		phone: DF.Data | None
		phone_ext: DF.Data | None
		place_of_issuance: DF.Literal["Ministry of Public Security", "Department of Police for Administrative Management of Social Order", "Department of Police for Registration, Residency Management, and National Population Data"]
		preferred_product_type: DF.TableMultiSelect[LeadProductItem]
		proposed_budget: DF.Link | None
		province: DF.Link | None
		purpose_lead: DF.Link | None
		qualification_status: DF.Literal["Unqualified", "Qualified"]
		qualified_by: DF.Link | None
		qualified_lead_date: DF.Datetime | None
		qualified_on: DF.Datetime | None
		region: DF.Link | None
		request_type: DF.Literal["Product Enquiry", "Request for Information", "Suggestions", "Other"]
		salutation: DF.Link | None
		source: DF.Link
		state: DF.Data | None
		status: DF.Literal["Lead", "Contacted", "Replied", "Interested", "Qualified", "Opportunity", "Converted", "Do Not Contact", "Spam"]
		stringee_data: DF.JSON | None
		tax_number: DF.Data | None
		territory: DF.Link | None
		title: DF.Data | None
		type: DF.Literal["Individual", "Company", "Consultant", "Channel Partner"]
		unsubscribed: DF.Check
		utm_campaign: DF.Link | None
		utm_content: DF.Data | None
		utm_medium: DF.Link | None
		utm_source: DF.Link | None
		website: DF.Data | None
		website_from_data: DF.JSON | None
		whatsapp_no: DF.Data | None
	# end: auto-generated types

	def onload(self):
		customer = frappe.db.get_value("Customer", {"lead_name": self.name})
		self.get("__onload").is_customer = customer
		load_address_and_contact(self)
		self.set_onload("linked_prospects", self.get_linked_prospects())

	def validate(self):
		self.set_full_name()
		self.set_lead_name()
		self.set_title()
		self.set_status()
		self.check_email_id_is_unique()
		self.check_phone_is_unique()
		self.validate_email_id()

	def before_insert(self):
		self.contact_doc = None
		if frappe.db.get_single_value("CRM Settings", "auto_creation_of_contact"):
			if self.utm_source == "Existing Customer" and self.customer:
				contact = frappe.db.get_value(
					"Dynamic Link",
					{"link_doctype": "Customer", "parenttype": "Contact", "link_name": self.customer},
					"parent",
				)
				if contact:
					self.contact_doc = frappe.get_doc("Contact", contact)
					return

			'''
			Pancake_data is not null when the leads are synced from Pancake
			'''
			if self.pancake_data:

				lead_source = self.check_lead_source()
				if lead_source:
					parsed_pancake_data = frappe.parse_json(self.pancake_data)
					existing_contact = self.check_contact(
						page_id=parsed_pancake_data.get("page_id"),
						conversation_id=parsed_pancake_data.get("conversation_id")
					)
					if not existing_contact:
						self.contact_doc = self.create_contact(lead_source)
					else:
						self.contact_doc = existing_contact
					if self.contact_doc:
						self.source = self.contact_doc.source
			else:
				self.contact_doc = self.create_contact()

		# leads created by email inbox only have the full name set
		if self.lead_name and not any([self.first_name, self.middle_name, self.last_name]):
			self.first_name, self.middle_name, self.last_name = parse_full_name(self.lead_name)

		if self.pancake_data:
			pancake_user_id = self.pancake_data.get("pancake_user_id", None)
			self.update_lead_owner(pancake_user_id)

	def before_save(self):
		self.update_lead_stage()
		self.update_qualification_status()
		self.fetch_region_from_province()
		self.update_first_reach_at()
		self.upsert_lead_source()
		self.update_pancake_lead_owner()
		self.process_notes()

	def process_notes(self):
		for note in self.notes:
			note.update_added_by()

	def update_pancake_lead_owner(self):
		try:
			if self.pancake_data:
				pancake_user_id = frappe.parse_json(self.pancake_data).get("pancake_user_id", None)
				if pancake_user_id and (not self.lead_owner or self.lead_owner == "tech@jemmia.vn"):
					self.update_lead_owner(pancake_user_id)
		except Exception as _:
			pass

	def update_lead_stage(self):
		if self.lead_stage=="Customer":
			return

		lead_stage = self.get_lead_stage()

		if lead_stage:
			self.lead_stage = lead_stage

		if  self.has_value_changed("lead_stage") \
			and  not self.qualified_lead_date \
			and self.lead_stage != "Lead" :
			self.qualified_lead_date = frappe.utils.now_datetime()

	def update_qualification_status(self):
		"""
		Update qualification status based on phone and province
		Only auto-qualifies when conditions are met, never auto-disqualifies
		Also set qualified_by and qualified_on when manually changed to Qualified
		"""
		# User manually changed to Qualified
		if self.has_value_changed("qualification_status") and self.qualification_status == "Qualified":
			if not self.qualified_by:
				self.qualified_by = frappe.session.user
			self.qualified_on = frappe.utils.now_datetime()
			return

		new_qualification_status = self.get_qualification_status()

		# Auto-qualification logic based on phone and province
		if (new_qualification_status == "Qualified" and self.qualification_status != "Qualified") or \
		   (self.qualification_status != "Qualified"):

			old_status = self.qualification_status
			self.qualification_status = new_qualification_status

			# Set qualified_by and qualified_on when moving to Qualified
			if self.qualification_status == "Qualified" and old_status != "Qualified":
				if not self.qualified_by:
					self.qualified_by = frappe.session.user
				self.qualified_on = frappe.utils.now_datetime()

	def update_lead_owner(self, pancake_user_id:str | None):
		"""
		update lead owner
		"""
		user = None

		if pancake_user_id:
			try:
				user = frappe.get_doc('User', {"pancake_id": pancake_user_id})
			except Exception:
				user = None

		# pancake id not exist == user off board
		# assign default mail config
		if not user:
			try:
				user = frappe.get_doc('User', {"email": config.DEFAULT_MAIL_OWNER})
			except Exception:
				user = None

		if user:
			self.lead_owner = user.name

	def fetch_region_from_province(self):
		if self.province:
			self.region = frappe.db.get_value("Province", self.province, "region")

	def update_first_reach_at(self):
		if self.pancake_data:
			parsed_pancake_data = frappe.parse_json(self.pancake_data)
			inserted_at_str = parsed_pancake_data.get("inserted_at", None)
			if inserted_at_str:
				inserted_at_dt = frappe.utils.get_datetime(inserted_at_str)
				if not self.first_reach_at:
					self.first_reach_at = inserted_at_dt
				else:
					first_reach_at_dt = frappe.utils.get_datetime(self.first_reach_at)
					if inserted_at_dt < first_reach_at_dt:
						self.first_reach_at = inserted_at_dt

	def upsert_lead_source(self):
		# Update source if source is None
		if self.source is None or self.source.strip() == "":
			if not self.pancake_data:
				return

			lead_source = self.check_lead_source()
			if not lead_source:
				return

			parsed_pancake_data = frappe.parse_json(self.pancake_data)
			check_contact = frappe.db.get_value(
				"Contact",
				{
					"pancake_page_id": parsed_pancake_data.get("page_id", None),
					"pancake_conversation_id": parsed_pancake_data.get("conversation_id", None),
					"pancake_customer_id": parsed_pancake_data.get("customer_id", None)
				},
			)

			if check_contact:
				self.contact_doc = frappe.get_doc("Contact", check_contact)
				self.source = self.contact_doc.source
				self.link_to_contact()
			else:
				self.contact_doc = self.create_contact(lead_source)
				if self.contact_doc:
					self.source = self.contact_doc.source
					self.link_to_contact()

	def check_contact(self, page_id, conversation_id):
		'''
		If contact with pancake data exists, do not create again
		'''
		existing_contact_name = frappe.db.get_value(
			"Contact",
			{
				"pancake_page_id": page_id,
				"pancake_conversation_id": conversation_id,
			},
			"name"
		)
		if existing_contact_name:
			return frappe.get_doc("Contact", existing_contact_name)

		return None

	def check_lead_source(self, pancake_data=None):
		lead_source = None
		parsed_pancake_data = None

		if pancake_data:
			parsed_pancake_data = pancake_data
		else:
			try:
				parsed_pancake_data = frappe.parse_json(self.pancake_data)
			except Exception:
				parsed_pancake_data = None

		if parsed_pancake_data is None:
			return
		if parsed_pancake_data.get("page_id", None):
			lead_source = frappe.db.get_value("Lead Source",
			{"pancake_page_id": parsed_pancake_data.get("page_id")}, ["name", "source_name", "pancake_platform" ])
			if lead_source is None or lead_source == "":
				lead_source = frappe.new_doc("Lead Source")

				pc_platform = parsed_pancake_data.get("platform", None)
				lead_source_prefix = ''
				lead_source_platform = None
				if "facebook" in pc_platform:
					lead_source_platform = "Facebook"
					lead_source_prefix = "FB"
				elif pc_platform == "zalo":
					lead_source_platform = "ZaloOA"
					lead_source_prefix = "ZOA"
				elif pc_platform == "personal_zalo":
					lead_source_platform = "Zalo"
					lead_source_prefix = "ZL"
				elif pc_platform == "personal_zalo_koc":
					lead_source_platform = "ZaloKOC"
					lead_source_prefix = "ZOA"
				elif "instagram" in pc_platform:
					lead_source_platform = "Instagram"
					lead_source_prefix = "IG"
				elif "tiktok" in pc_platform:
					lead_source_platform = "Tiktok"
					lead_source_prefix = "TT"

				source_name = None
				if lead_source_prefix:
					source_name = f"{lead_source_prefix} {parsed_pancake_data.get('page_name', '')}"
				else:
					source_name = parsed_pancake_data.get("page_name", '')

				lead_source.update({
					"source_name": source_name,
					"pancake_page_id": parsed_pancake_data.get("page_id", None),
					"pancake_platform": lead_source_platform
				})
				lead_source.insert(ignore_permissions=True)
				lead_source.reload()
				lead_source = frappe.db.get_value("Lead Source", {"name": lead_source.name}, ["name", "source_name", "pancake_platform"])

		return lead_source

	def after_insert(self):
		if self.contact_doc:
			contact_link = frappe.get_value("Dynamic Link", {
					"link_doctype": self.doctype,
					"link_name": self.name,
					"parenttype": "Contact",
					"parent": self.contact_doc.name
			}, "name")
			if contact_link:
				return
		self.link_to_contact()

	def on_update(self):
		self.update_prospect()
		self.update_assignment_status()
		#Trigger auto create Opportunity
		self.create_opportunity()

	def on_trash(self):
		frappe.db.set_value("Issue", {"lead": self.name}, "lead", None)
		try:
			delete_contact_and_address(self.doctype, self.name)
		except Exception:
			frappe.log_error(
				title=f"Error deleting contact/address for Lead {self.name}",
				message=frappe.get_traceback()
			)
		finally:
			frappe.db.delete(
				"Dynamic Link",
				{
					"link_doctype": self.doctype,
					"link_name": self.name,
				}
			)
		self.remove_link_from_prospect()

	def set_full_name(self):
		if self.first_name:
			self.lead_name = " ".join(
				filter(None, [self.salutation, self.first_name, self.middle_name, self.last_name])
			)

	def set_lead_name(self):
		if not self.lead_name:
			# Check for leads being created through data import
			if not self.company_name and not self.email_id and not self.flags.ignore_mandatory:
				frappe.throw(_("A Lead requires either a person's name or an organization's name"))
			elif self.company_name:
				self.lead_name = self.company_name
			else:
				self.lead_name = self.email_id.split("@")[0]

	def set_title(self):
		self.title = self.company_name or self.lead_name

	def check_email_id_is_unique(self):
		if self.email_id:
			# validate email is unique
			if not frappe.db.get_single_value("CRM Settings", "allow_lead_duplication_based_on_emails"):
				duplicate_leads = frappe.get_all(
					"Lead", filters={"email_id": self.email_id, "name": ["!=", self.name]}
				)
				duplicate_leads = [
					frappe.bold(get_link_to_form("Lead", lead.name)) for lead in duplicate_leads
				]

				if duplicate_leads:
					frappe.throw(
						_("Email Address must be unique, it is already used in {0}").format(
							comma_and(duplicate_leads)
						),
						frappe.DuplicateEntryError,
					)

	def validate_email_id(self):
		if self.email_id:
			if not self.flags.ignore_email_validation:
				validate_email_address(self.email_id, throw=True)

			if self.email_id == self.lead_owner:
				frappe.throw(_("Lead Owner cannot be same as the Lead Email Address"))

			if self.is_new() or not self.image:
				self.image = has_gravatar(self.email_id)

	def check_phone_is_unique(self):
		if self.phone:
			# Validate phone number is unique
			filters = {"phone": self.phone}
			if self.name:
				filters["name"] = ["!=", self.name]
			duplicate_leads = frappe.get_all("Lead", filters=filters)
			duplicate_leads = [
				frappe.bold(get_link_to_form("Lead", lead.name)) for lead in duplicate_leads
			]
			if duplicate_leads:
				frappe.throw(
					_("Phone Number must be unique, it is already used in {0}").format(
						comma_and(duplicate_leads)
					),
					frappe.DuplicateEntryError,
				)

	def link_to_contact(self):
		# update contact links
		if self.contact_doc:
			self.contact_doc.append(
				"links", {"link_doctype": "Lead", "link_name": self.name, "link_title": self.lead_name}
			)
			self.contact_doc.save()

	def link_to_contacts(self, pancake_data):
		try:
			page_id = pancake_data.get("page_id")
			conversation_id = pancake_data.get("conversation_id")

			self.contact_doc = self.check_contact(
				page_id=page_id,
				conversation_id=conversation_id
			)

			if not self.contact_doc:
				self.contact_doc = self.create_contact(pancake_data=pancake_data)
			else:
				self.update_contact(self.contact_doc, pancake_data=pancake_data)

			if self.contact_doc:
				contact_link = frappe.get_value("Dynamic Link", {
						"link_doctype": self.doctype,
						"link_name": self.name,
						"parenttype": "Contact",
						"parent": self.contact_doc.name
				}, "name")
				if not contact_link:
					self.link_to_contact()

				self.set_first_lead_source()

		except Exception as e:
			frappe.log_error(f"Error link_to_contacts {e}")

	def update_contact(self, contact: Contact, pancake_data):
		try:
			if not contact or not pancake_data:
				return

			has_changed = False

			fields_map = [
				("latest_message_at", "last_message_time"),
				("updated_at", "pancake_updated_at"),
				("updated_at", "updated_at"),
				("customer_id", "pancake_customer_id"),
				("inserted_at", "pancake_inserted_at"),
				("inserted_at", "inserted_at"),
				("ad_ids", "ad_ids")
			]

			for pancake_field, contact_field in fields_map:
				value = pancake_data.get(pancake_field)

				if contact_field == "ad_ids" and isinstance(value, list):
					value = json.dumps(value)

				if value is not None and contact.get(contact_field) != value:
					contact.set(contact_field, value)
					has_changed = True

			if self.phone:
				phone_exists = False
				has_primary_phone = False
				has_primary_mobile = False

				for d in contact.get("phone_nos", []):
					if d.phone == self.phone:
						phone_exists = True
					if d.get("is_primary_phone"):
						has_primary_phone = True
					if d.get("is_primary_mobile_no"):
						has_primary_mobile = True

				if not phone_exists:
					phone_owner = frappe.db.get_value("Lead", {"phone": self.phone}, "name")
					if phone_owner and phone_owner != self.name:
						frappe.logger().warning(
							f"update_contact: skipping phone {self.phone} — already owned by lead {phone_owner}"
						)
					else:
						contact.append("phone_nos", {
							"phone": self.phone,
							"is_primary_phone": 0 if has_primary_phone else 1,
							"is_primary_mobile_no": 0 if has_primary_mobile else 1
						})
						has_changed = True

			if has_changed:
				contact.save(ignore_permissions=True)

		except Exception as e:
			frappe.log_error(f"Error update_contact: {e}")

	def set_first_lead_source(self):
		try:
			source = frappe.db.sql(
				'''
				SELECT tc.source
				FROM `tabDynamic Link` as tdl
				JOIN `tabContact` as tc ON tdl.parent = tc.name
				WHERE tdl.link_name = %s
					AND tdl.link_doctype = 'Lead'
					AND tdl.parenttype = 'Contact'
					AND tc.inserted_at IS NOT NULL
				ORDER BY tc.inserted_at ASC
				LIMIT 1
				''',
				(self.name,)
			)

			if source and source[0][0]:
				self.db_set("source", source[0][0])

		except Exception as e:
			frappe.log_error(f"Error set_first_lead_source {e}")

	def update_prospect(self):
		lead_row_name = frappe.db.get_value("Prospect Lead", filters={"lead": self.name}, fieldname="name")
		if lead_row_name:
			lead_row = frappe.get_doc("Prospect Lead", lead_row_name)
			lead_row.update(
				{
					"lead_name": self.lead_name,
					"email": self.email_id,
					"mobile_no": self.mobile_no,
					"lead_owner": self.lead_owner,
					"status": self.status,
				}
			)
			lead_row.db_update()

	def update_assignment_status(self):
		"""
		Update is_assigned field based on assignment status
		Sets is_assigned = 1 when lead is assigned to someone
		Sets is_assigned = 0 when all assignments are removed
		Handle all possible states of _assign:
		None, '', '[]' or '["user@example.com"]'
		"""
		if self.modified_by == "tech@jemmia.vn":
			return

		_assign = frappe.db.get_value('Lead', self.name, '_assign')
		assign_list = []

		if _assign:
			try:
				assign_list = json.loads(_assign)
			except (json.JSONDecodeError, TypeError):
				assign_list = []

		should_be_assigned = 1 if assign_list else 0
		if self.is_assigned != should_be_assigned:
			frappe.db.set_value('Lead', self.name, 'is_assigned', should_be_assigned)

	def remove_link_from_prospect(self):
		prospects = self.get_linked_prospects()

		for d in prospects:
			prospect = frappe.get_doc("Prospect", d.parent)
			if len(prospect.get("leads")) == 1:
				prospect.delete(ignore_permissions=True)
			else:
				to_remove = None
				for d in prospect.get("leads"):
					if d.lead == self.name:
						to_remove = d

				if to_remove:
					prospect.remove(to_remove)
					prospect.save(ignore_permissions=True)

	def get_linked_prospects(self):
		return frappe.get_all(
			"Prospect Lead",
			filters={"lead": self.name},
			fields=["parent"],
		)

	def has_customer(self):
		return frappe.db.get_value("Customer", {"lead_name": self.name})

	def has_opportunity(self):
		return frappe.db.get_value("Opportunity", {"party_name": self.name, "status": ["!=", "Lost"]})

	def has_quotation(self):
		return frappe.db.get_value(
			"Quotation", {"party_name": self.name, "docstatus": 1, "status": ["!=", "Lost"]}
		)

	def has_lost_quotation(self):
		return frappe.db.get_value("Quotation", {"party_name": self.name, "docstatus": 1, "status": "Lost"})

	def create_opportunity(self):
		"""
		auto create Opportunity when lead was Qualified
		"""

		if self.qualification_status != "Qualified":
			return

		# Get lastest Opportunity
		latest_opportunity = frappe.db.get_value("Opportunity", 
			{"party_name": self.name, "opportunity_from": "Lead"},
			["name", "status", "creation"],
			as_dict=True,
			order_by="creation desc"
		)

		if latest_opportunity:
			if latest_opportunity.status in ["Open", "Quotation", "Negotiation"]:
				return
			
			# If Opportunity was closed, check time
			# Affter `days_limit` day, Lead can create new Opportunity
			days_limit = 30 
			
			diff_days = date_diff(now_datetime(), latest_opportunity.creation)
			if diff_days < days_limit:
				return

		opportunity = make_opportunity(self.name)

		opportunity.insert(ignore_permissions=True)
	@frappe.whitelist()
	def create_prospect_and_contact(self, data):
		data = frappe._dict(data)
		if data.create_contact:
			self.create_contact()

		if data.create_prospect:
			self.create_prospect(data.prospect_name)

	def create_contact(self, lead_source=None, pancake_data=None):
		if not self.lead_name:
			self.set_full_name()
			self.set_lead_name()

		contact = frappe.new_doc("Contact")

		parsed_pancake_data = pancake_data
		if not parsed_pancake_data and self.pancake_data:
			try:
				parsed_pancake_data = frappe.parse_json(self.pancake_data)
			except Exception:
				parsed_pancake_data = None

		pancake_dict = parsed_pancake_data or {}

		# Determine source from pancake platform
		derived_source = self.source
		if pancake_dict:
			lead_source_data = self.check_lead_source(pancake_data=pancake_dict)
			if lead_source_data:
				derived_source = lead_source_data[0]

		contact.update(
			{
				"first_name": self.first_name or self.lead_name,
				"last_name": self.last_name,
				"salutation": self.salutation,
				"source": derived_source,
				"gender": self.gender,
				"designation": self.job_title,
				"company_name": self.company_name,
				"pancake_conversation_id": pancake_dict.get("conversation_id") or None,
				"pancake_customer_id": pancake_dict.get("customer_id") or None,
				"pancake_inserted_at": pancake_dict.get("inserted_at") or None,
				"inserted_at": pancake_dict.get("inserted_at") or None,
				"pancake_updated_at": pancake_dict.get("updated_at") or None,
				"pancake_page_id": pancake_dict.get("page_id") or None,
				"can_inbox": pancake_dict.get("can_inbox") or 0,
				"last_message_time" :  pancake_dict.get("latest_message_at") or None,
				"ad_ids": json.dumps(pancake_dict.get("ad_ids")) if isinstance(pancake_dict.get("ad_ids"), list) else (pancake_dict.get("ad_ids") or None)
			}
		)

		if self.email_id:
			contact.append("email_ids", {"email_id": self.email_id, "is_primary": 1})

		if self.phone:
			contact.append("phone_nos", {"phone": self.phone, "is_primary_phone": 1})

		if self.mobile_no:
			contact.append("phone_nos", {"phone": self.mobile_no, "is_primary_mobile_no": 1})

		if lead_source:
			contact.update({
				"source": lead_source[0],
				"source_group": lead_source[2]
			})
		try:
			contact.insert(
				ignore_permissions=True,
				raise_direct_exception=True,
			)
			contact.reload()
			return contact

		except frappe.LinkValidationError as e:
			frappe.log_error(
				f"Failed to create contact for lead (LinkValidationError): {e!s}")
			frappe.throw(_(f"Failed to create contact for lead (LinkValidationError): {e!s}."))
		except Exception as e:
			frappe.log_error(f"Error create_contact: {e}")
			return None
		return None

	def create_prospect(self, company_name):
		try:
			prospect = frappe.new_doc("Prospect")

			prospect.company_name = company_name or self.company_name
			prospect.no_of_employees = self.no_of_employees
			prospect.industry = self.industry
			prospect.market_segment = self.market_segment
			prospect.annual_revenue = self.annual_revenue
			prospect.territory = self.territory
			prospect.fax = self.fax
			prospect.website = self.website
			prospect.prospect_owner = self.lead_owner
			prospect.company = self.company
			prospect.notes = self.notes

			prospect.append(
				"leads",
				{
					"lead": self.name,
					"lead_name": self.lead_name,
					"email": self.email_id,
					"mobile_no": self.mobile_no,
					"lead_owner": self.lead_owner,
					"status": self.status,
				},
			)
			prospect.flags.ignore_permissions = True
			prospect.flags.ignore_mandatory = True
			prospect.save()
		except frappe.DuplicateEntryError:
			frappe.throw(_("Prospect {0} already exists").format(company_name or self.company_name))

	def get_lead_stage(self):

		if not self.phone or not self.province:
			return "Lead"

		#TODO
		# hide this feature
		# if not self.budget_lead or not self.purpose_lead or not self.preferred_product_type:
		# 	return "Qualified Lead"


		# return "Opportunity"

		return "Qualified Lead"
	def get_qualification_status(self):
		"""
		Determine qualification status based on:
		  1. Must have phone and province
		  2. Must have preferred_product_type and budget_lead
		Only auto-qualifies, never auto-disqualifies.
		"""
		if self.phone and self.province:
			if self.source == 'CRM-LEAD-SOURCE-0000023':
				return "Qualified"
			elif self.preferred_product_type and self.budget_lead:
				return "Qualified"

		return self.qualification_status

	def normalize_phone(self):
		if self.phone:
			from erpnext.crm.doctype.lead.lead_methods import normalize_phone_number
			self.phone = normalize_phone_number(self.phone)

@frappe.whitelist()
def make_customer(source_name, target_doc=None):
	return _make_customer(source_name, target_doc)


def _make_customer(source_name, target_doc=None, ignore_permissions=False):
	def set_missing_values(source, target):
		if source.company_name:
			target.customer_type = "Company"
			target.customer_name = source.company_name
		else:
			target.customer_type = "Individual"
			target.customer_name = source.lead_name

		if not target.customer_group:
			target.customer_group = frappe.db.get_default("Customer Group")

		address = get_default_address("Lead", source.name)
		contact = get_default_contact("Lead", source.name)
		if address:
			target.customer_primary_address = address
		if contact:
			target.customer_primary_contact = contact

	doclist = get_mapped_doc(
		"Lead",
		source_name,
		{
			"Lead": {
				"doctype": "Customer",
				"field_map": {
					"name": "lead_name",
					"company_name": "customer_name",
					"contact_no": "phone_1",
					"fax": "fax_1",
				},
				"field_no_map": ["disabled"],
			}
		},
		target_doc,
		set_missing_values,
		ignore_permissions=ignore_permissions,
	)

	return doclist


@frappe.whitelist()
def make_opportunity(source_name, target_doc=None):
	def set_missing_values(source, target):
		_set_missing_values(source, target)

	target_doc = get_mapped_doc(
		"Lead",
		source_name,
		{
			"Lead": {
				"doctype": "Opportunity",
				"field_map": {
					"doctype": "opportunity_from",
					"name": "party_name",
					"lead_name": "contact_display",
					"company_name": "customer_name",
					"email_id": "contact_email",
					"mobile_no": "contact_mobile",
					"lead_owner": "opportunity_owner",
					"notes": "notes",
				},
			}
		},
		target_doc,
		set_missing_values,
	)

	return target_doc


@frappe.whitelist()
def make_quotation(source_name, target_doc=None):
	def set_missing_values(source, target):
		_set_missing_values(source, target)

	target_doc = get_mapped_doc(
		"Lead",
		source_name,
		{"Lead": {"doctype": "Quotation", "field_map": {"name": "party_name"}}},
		target_doc,
		set_missing_values,
	)

	target_doc.quotation_to = "Lead"
	target_doc.run_method("set_missing_values")
	target_doc.run_method("set_other_charges")
	target_doc.run_method("calculate_taxes_and_totals")

	return target_doc


def _set_missing_values(source, target):
	address = frappe.get_all(
		"Dynamic Link",
		{
			"link_doctype": source.doctype,
			"link_name": source.name,
			"parenttype": "Address",
		},
		["parent"],
		limit=1,
	)

	contact = frappe.get_all(
		"Dynamic Link",
		{
			"link_doctype": source.doctype,
			"link_name": source.name,
			"parenttype": "Contact",
		},
		["parent"],
		limit=1,
	)

	if address:
		target.customer_address = address[0].parent

	if contact:
		target.contact_person = contact[0].parent


@frappe.whitelist()
def get_lead_details(lead, posting_date=None, company=None, doctype=None):
	if not lead:
		return {}

	from erpnext.accounts.party import set_address_details

	out = frappe._dict()

	lead_doc = frappe.get_doc("Lead", lead)
	lead = lead_doc

	out.update(
		{
			"territory": lead.territory,
			"customer_name": lead.company_name or lead.lead_name,
			"contact_display": " ".join(filter(None, [lead.lead_name])),
			"contact_email": lead.email_id,
			"contact_mobile": lead.mobile_no,
			"contact_phone": lead.phone,
		}
	)

	set_address_details(out, lead, "Lead", doctype=doctype, company=company)

	taxes_and_charges = set_taxes(
		None,
		"Lead",
		posting_date,
		company,
		billing_address=out.get("customer_address"),
		shipping_address=out.get("shipping_address_name"),
	)
	if taxes_and_charges:
		out["taxes_and_charges"] = taxes_and_charges

	return out


@frappe.whitelist()
def make_lead_from_communication(communication, ignore_communication_links=False):
	"""raise a issue from email"""

	doc = frappe.get_doc("Communication", communication)
	lead_name = None
	if doc.sender:
		lead_name = frappe.db.get_value("Lead", {"email_id": doc.sender})
	if not lead_name and doc.phone_no:
		lead_name = frappe.db.get_value("Lead", {"mobile_no": doc.phone_no})
	if not lead_name:
		lead = frappe.get_doc(
			{
				"doctype": "Lead",
				"lead_name": doc.sender_full_name,
				"email_id": doc.sender,
				"mobile_no": doc.phone_no,
			}
		)
		lead.flags.ignore_mandatory = True
		lead.flags.ignore_permissions = True
		lead.insert()

		lead_name = lead.name

	link_communication_to_document(doc, "Lead", lead_name, ignore_communication_links)
	return lead_name


def get_lead_with_phone_number(number):
	if not number:
		return

	leads = frappe.get_all(
		"Lead",
		or_filters={
			"phone": ["like", f"%{number}"],
			"whatsapp_no": ["like", f"%{number}"],
			"mobile_no": ["like", f"%{number}"],
		},
		limit=1,
		order_by="creation DESC",
	)

	lead = leads[0].name if leads else None

	return lead


@frappe.whitelist()
def add_lead_to_prospect(lead, prospect):
	prospect = frappe.get_doc("Prospect", prospect)
	prospect.append("leads", {"lead": lead})
	prospect.save(ignore_permissions=True)

	carry_forward_communication_and_comments = frappe.db.get_single_value(
		"CRM Settings", "carry_forward_communication_and_comments"
	)

	if carry_forward_communication_and_comments:
		copy_comments("Lead", lead, prospect)
		link_communications("Lead", lead, prospect)
	link_open_events("Lead", lead, prospect)

	frappe.msgprint(
		_("Lead {0} has been added to prospect {1}.").format(frappe.bold(lead), frappe.bold(prospect.name)),
		title=_("Lead -> Prospect"),
		indicator="green",
	)
