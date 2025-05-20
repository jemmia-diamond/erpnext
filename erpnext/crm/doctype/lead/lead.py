# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
import frappe
from frappe import _
from frappe.contacts.address_and_contact import (
	delete_contact_and_address,
	load_address_and_contact,
)
from frappe.email.inbox import link_communication_to_document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import comma_and, get_link_to_form, has_gravatar, validate_email_address

from erpnext.accounts.party import set_taxes
from erpnext.controllers.selling_controller import SellingController
from erpnext.crm.utils import CRMNote, copy_comments, link_communications, link_open_events
from erpnext.selling.doctype.customer.customer import parse_full_name


class Lead(SellingController, CRMNote):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from erpnext.crm.doctype.crm_note.crm_note import CRMNote
		from erpnext.crm.doctype.lead_channel.lead_channel import LeadChannel
		from erpnext.crm.doctype.lead_diamond.lead_diamond import LeadDiamond
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
		campaign_name: DF.Link | None
		ceo_name: DF.Data | None
		check_duplicate: DF.Link | None
		company: DF.Link | None
		company_name: DF.Data | None
		customer: DF.Link | None
		date_of_issuance: DF.Date | None
		demand_notes: DF.SmallText | None
		disabled: DF.Check
		email_id: DF.Data | None
		expected_delivery_date: DF.Date | None
		fax: DF.Data | None
		first_channel: DF.Link | None
		first_name: DF.Data | None
		gender: DF.Link | None
		image: DF.AttachImage | None
		industry: DF.Link | None
		job_title: DF.Data | None
		language: DF.Link | None
		last_name: DF.Data | None
		lead_name: DF.Data | None
		lead_owner: DF.Link | None
		lead_received_date: DF.Datetime | None
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
		preferred_diamond: DF.Table[LeadDiamond]
		preferred_product_type: DF.TableMultiSelect[LeadProductItem]
		province: DF.Link | None
		purpose_lead: DF.Link | None
		qualification_status: DF.Literal["Unqualified", "In Process", "Qualified"]
		qualified_by: DF.Link | None
		qualified_on: DF.Date | None
		region: DF.Link | None
		request_type: DF.Literal["Product Enquiry", "Request for Information", "Suggestions", "Other"]
		salutation: DF.Link | None
		source: DF.Link | None
		status: DF.Literal["Lead", "Open", "Replied", "Opportunity", "Quotation", "Lost Quotation", "Interested", "Converted", "Do Not Contact", "Spam"]
		stringee_data: DF.JSON | None
		table_uzxd: DF.Table[LeadChannel]
		tax_number: DF.Data | None
		territory: DF.Link | None
		title: DF.Data | None
		type: DF.Literal["Individual", "Company", "Consultant", "Channel Partner"]
		unsubscribed: DF.Check
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
			if self.source == "Existing Customer" and self.customer:
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
					self.contact_doc = self.create_contact(lead_source)
					if self.contact_doc:
						self.source = self.contact_doc.source
			else:
				self.contact_doc = self.create_contact()

		# leads created by email inbox only have the full name set
		if self.lead_name and not any([self.first_name, self.middle_name, self.last_name]):
			self.first_name, self.middle_name, self.last_name = parse_full_name(self.lead_name)

	def check_lead_source(self):
		lead_source = None
		parsed_pancake_data = None
		try:
			parsed_pancake_data = frappe.parse_json(self.pancake_data)
		except Exception as e:
			parsed_pancake_data = None
		if parsed_pancake_data is None:
			return 
		if parsed_pancake_data.get("page_id", None):
			lead_source = frappe.db.get_value("Lead Source", 
			{"pancake_page_id": parsed_pancake_data.get("page_id")}, ["name", "source_name", "pancake_platform" ])
			if lead_source is None or lead_source == "":
				lead_source = frappe.new_doc("Lead Source")

				pc_platform = parsed_pancake_data.get("platform", None)
				lead_source_platform = None
				if "facebook" in pc_platform:
					lead_source_platform = "Facebook"
				elif "zalo" in pc_platform:
					lead_source_platform = "Zalo"
				elif "instagram" in pc_platform:
					lead_source_platform = "Instagram"
				elif "tiktok" in pc_platform:
					lead_source_platform = "Tiktok"	

				lead_source.update({
					"source_name": "Unspecified",
					"pancake_page_id": parsed_pancake_data.get("page_id", None),
					"pancake_platform": lead_source_platform
				})
				lead_source.insert(ignore_permissions=True)
				lead_source.reload()
				lead_source = frappe.db.get_value("Lead Source", {"name": lead_source.name}, ["name", "source_name", "pancake_platform"])
		
		return lead_source

	def after_insert(self):
		self.link_to_contact()

	def on_update(self):
		self.update_prospect()

	def on_trash(self):
		frappe.db.set_value("Issue", {"lead": self.name}, "lead", None)
		delete_contact_and_address(self.doctype, self.name)
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

	@frappe.whitelist()
	def create_prospect_and_contact(self, data):
		data = frappe._dict(data)
		if data.create_contact:
			self.create_contact()

		if data.create_prospect:
			self.create_prospect(data.prospect_name)

	def create_contact(self, lead_source=None):
		if not self.lead_name:
			self.set_full_name()
			self.set_lead_name()

		contact = frappe.new_doc("Contact")

		parsed_pancake_data = None
		if self.pancake_data:
			try:
				parsed_pancake_data = frappe.parse_json(self.pancake_data)
			except Exception as e:
				parsed_pancake_data = None

		contact.update(
			{
				"first_name": self.first_name or self.lead_name,
				"last_name": self.last_name,
				"salutation": self.salutation,
				"source": self.source,
				"gender": self.gender,
				"designation": self.job_title,
				"company_name": self.company_name,
				"pancake_conversation_id": parsed_pancake_data.get("conversation_id") if parsed_pancake_data and parsed_pancake_data.get("conversation_id") else None,
				"pancake_customer_id": parsed_pancake_data.get("customer_id") if parsed_pancake_data and parsed_pancake_data.get("customer_id") else None,
				"inserted_at": parsed_pancake_data.get("inserted_at") if parsed_pancake_data and parsed_pancake_data.get("inserted_at") else None,
				"pancake_updated_at": parsed_pancake_data.get("updated_at") if parsed_pancake_data and parsed_pancake_data.get("updated_at") else None,
				"pancake_page_id": parsed_pancake_data.get("page_id") if parsed_pancake_data and parsed_pancake_data.get("page_id") else None,
				"can_inbox": parsed_pancake_data.get("can_inbox") if parsed_pancake_data and parsed_pancake_data.get("can_inbox") else 0,
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
				f"Failed to create contact for lead (LinkValidationError): {str(e)}")
			frappe.throw(_(f"Failed to create contact for lead (LinkValidationError): {str(e)}."))		
		except Exception as e:
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

		target.customer_group = frappe.db.get_default("Customer Group")

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
					"campaign_name": "campaign",
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
def get_lead_details(lead, posting_date=None, company=None):
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

	set_address_details(out, lead, "Lead", company=company)

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



