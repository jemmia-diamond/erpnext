# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import json

import frappe
import frappe.defaults
from frappe import _, msgprint, qb
from frappe.contacts.address_and_contact import (
	delete_contact_and_address,
	load_address_and_contact,
)
from frappe.model.mapper import get_mapped_doc
from frappe.model.naming import set_name_by_naming_series, set_name_from_naming_options
from frappe.model.utils.rename_doc import update_linked_doctypes
from frappe.utils import cint, cstr, flt, get_formatted_email, today, getdate, add_months, nowdate
from frappe.utils.deprecations import deprecated
from frappe.utils.user import get_users_with_role

from erpnext.accounts.party import get_dashboard_info, validate_party_accounts
from erpnext.controllers.website_list_for_contact import add_role_for_portal_user
from erpnext.utilities.transaction_base import TransactionBase
from erpnext.config.config import config
from erpnext.selling.doctype.coupon.coupon import update_customers_coupons
import requests

class CustomerRank:
	NO_RANK = "No Rank"
	SILVER = "Silver"
	GOLD = "Gold"
	PLATINUM = "Platinum"

class RankThreshold:
	# All revenue are in VND

	NO_REVENUE = 0
	PLATINUM_PURCHASE = 1_000_000_000
	GOLD_PURCHASE = 300_000_000
	PLATINUM_WITH_REFERRAL = 2_000_000_000
	GOLD_WITH_REFERRAL = 500_000_000

RANK_ORDER = {
	CustomerRank.NO_RANK: 0,
	CustomerRank.SILVER: 1,
	CustomerRank.GOLD: 2,
	CustomerRank.PLATINUM: 3
}

class Customer(TransactionBase):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from erpnext.accounts.doctype.allowed_to_transact_with.allowed_to_transact_with import AllowedToTransactWith
		from erpnext.accounts.doctype.party_account.party_account import PartyAccount
		from erpnext.selling.doctype.coupon.coupon import Coupon
		from erpnext.selling.doctype.customer_credit_limit.customer_credit_limit import CustomerCreditLimit
		from erpnext.selling.doctype.sales_team.sales_team import SalesTeam
		from erpnext.utilities.doctype.portal_user.portal_user import PortalUser
		from frappe.types import DF

		account_manager: DF.Link | None
		accounts: DF.Table[PartyAccount]
		actual_cumulative_revenue: DF.Currency
		available_point_amount: DF.Float
		back_image: DF.AttachImage | None
		bank_account: DF.Link | None
		birth_date: DF.Date | None
		bizfly_customer_number: DF.Data | None
		bizfly_id: DF.Data | None
		buyback_revenue: DF.Currency
		cashback: DF.Currency
		ceo_name: DF.Data | None
		companies: DF.Table[AllowedToTransactWith]
		company_name: DF.Data | None
		coupon_table: DF.Table[Coupon]
		credit_limits: DF.Table[CustomerCreditLimit]
		cumulative_revenue: DF.Currency
		customer_details: DF.Text | None
		customer_group: DF.Link | None
		customer_journey: DF.SmallText | None
		customer_name: DF.Data
		customer_pos_id: DF.Data | None
		customer_primary_address: DF.Link | None
		customer_primary_contact: DF.Link | None
		customer_rank: DF.Literal["No Rank", "Silver", "Gold", "Platinum"]
		customer_type: DF.Literal["Company", "Individual", "Partnership"]
		customer_website: DF.Data | None
		date_of_issuance: DF.Date | None
		date_of_passport_issuance: DF.Date | None
		default_bank_account: DF.Link | None
		default_commission_rate: DF.Float
		default_currency: DF.Link | None
		default_price_list: DF.Link | None
		default_sales_partner: DF.Link | None
		disabled: DF.Check
		dn_required: DF.Check
		doc_image: DF.AttachImage | None
		email_id: DF.ReadOnly | None
		first_source: DF.Link | None
		front_image: DF.AttachImage | None
		gender: DF.Link | None
		haravan_id: DF.Data | None
		image: DF.AttachImage | None
		industry: DF.Link | None
		invoice_type: DF.Literal["Individual", "Company"]
		is_frozen: DF.Check
		is_internal_customer: DF.Check
		language: DF.Link | None
		lead_name: DF.Link | None
		loyalty_program: DF.Link | None
		loyalty_program_tier: DF.Data | None
		market_segment: DF.Link | None
		mobile_no: DF.ReadOnly | None
		naming_series: DF.Literal["CUST-.YYYY.-"]
		no_of_employees: DF.Data | None
		opportunity_name: DF.Link | None
		passport_expiry_date: DF.Date | None
		passport_id: DF.Data | None
		payment_terms: DF.Link | None
		pending_cashback: DF.Currency
		pending_point: DF.Float
		person_name: DF.Data | None
		personal_document_type: DF.Literal["CCCD", "Passport"]
		personal_id: DF.Data | None
		personal_tax_id: DF.Data | None
		phone: DF.ReadOnly | None
		place_of_issuance: DF.Literal["", "B\u1ed9 C\u00f4ng An", "C\u1ee5c C\u1ea3nh s\u00e1t QLHC v\u1ec1 TTXH", "C\u1ee5c C\u1ea3nh s\u00e1t \u0111\u0103ng k\u00fd, qu\u1ea3n l\u00fd c\u01b0 tr\u00fa v\u00e0 d\u1eef li\u1ec7u qu\u1ed1c gia v\u1ec1 d\u00e2n c\u01b0"]
		place_of_passport_issuance: DF.Link | None
		portal_users: DF.Table[PortalUser]
		primary_address: DF.SmallText | None
		primary_contact: DF.SmallText | None
		priority_bank_account: DF.Link | None
		priority_login_date: DF.Date | None
		prospect_name: DF.Link | None
		purchase_amount_last_12_months: DF.Currency
		rank: DF.Literal["No Rank", "Silver", "Gold", "Platinum"]
		rank_expired_date: DF.Date | None
		rank_score_12m: DF.Currency
		rank_updated_at: DF.Date | None
		referral_cumulative_revenue: DF.Currency
		referrals_revenue: DF.Currency
		represents_company: DF.Link | None
		sales_team: DF.Table[SalesTeam]
		salutation: DF.Link | None
		so_required: DF.Check
		tax_category: DF.Link | None
		tax_id: DF.Data | None
		tax_number: DF.Data | None
		tax_withholding_category: DF.Link | None
		territory: DF.Link | None
		total_cumulative_revenue: DF.Currency
		total_referral_point: DF.Float
		true_cumulative_revenue: DF.Currency
		vat_address: DF.Data | None
		vat_email: DF.Data | None
		vat_name: DF.Data | None
		website: DF.Data | None
		withdraw_cash_amount: DF.Currency
		withdraw_cash_amount_pending: DF.Currency
		withdraw_cashback: DF.Currency
		withdraw_point: DF.Float
	# end: auto-generated types

	def onload(self):
		# Load address and contacts in `__onload`
		load_address_and_contact(self)
		self.load_dashboard_info()

	def load_dashboard_info(self):
		info = get_dashboard_info(self.doctype, self.name, self.loyalty_program)
		self.set_onload("dashboard_info", info)

	def get_customer_name(self):
		if frappe.db.get_value("Customer", self.customer_name) and not frappe.flags.in_import:
			count = frappe.db.sql(
				"""select ifnull(MAX(CAST(SUBSTRING_INDEX(name, ' ', -1) AS UNSIGNED)), 0) from tabCustomer
				 where name like %s""",
				f"%{self.customer_name} - %",
				as_list=1,
			)[0][0]
			count = cint(count) + 1

			new_customer_name = f"{self.customer_name} - {cstr(count)}"

			msgprint(
				_("Changed customer name to '{}' as '{}' already exists.").format(
					new_customer_name, self.customer_name
				),
				title=_("Note"),
				indicator="yellow",
			)

			return new_customer_name

		return self.customer_name

	def after_insert(self):
		"""If customer created from Lead, update customer id in quotations, opportunities"""
		self.update_lead_status()

	def validate(self):
		self.flags.is_new_doc = self.is_new()
		self.flags.old_lead = self.lead_name
		validate_party_accounts(self)
		self.validate_credit_limit_on_change()
		self.set_loyalty_program()
		self.check_customer_group_change()
		self.validate_default_bank_account()
		self.validate_internal_customer()
		self.add_role_for_user()
		self.validate_currency_for_receivable_payable_and_advance_account()

		# set loyalty program tier
		if frappe.db.exists("Customer", self.name):
			customer = frappe.get_doc("Customer", self.name)
			if self.loyalty_program == customer.loyalty_program and not self.loyalty_program_tier:
				self.loyalty_program_tier = customer.loyalty_program_tier

		if self.sales_team:
			if sum(member.allocated_percentage or 0 for member in self.sales_team) != 100:
				frappe.throw(_("Total contribution percentage should be equal to 100"))

	@frappe.whitelist()
	def get_customer_group_details(self):
		doc = frappe.get_doc("Customer Group", self.customer_group)
		self.accounts = []
		self.credit_limits = []
		self.payment_terms = self.default_price_list = ""

		tables = [["accounts", "account"], ["credit_limits", "credit_limit"]]
		fields = ["payment_terms", "default_price_list"]

		for row in tables:
			table, field = row[0], row[1]
			if not doc.get(table):
				continue

			for entry in doc.get(table):
				child = self.append(table)
				child.update({"company": entry.company, field: entry.get(field)})

		for field in fields:
			if not doc.get(field):
				continue
			self.update({field: doc.get(field)})

		self.save()

	def check_customer_group_change(self):
		frappe.flags.customer_group_changed = False

		if not self.get("__islocal"):
			if self.customer_group != frappe.db.get_value("Customer", self.name, "customer_group"):
				frappe.flags.customer_group_changed = True

	def validate_default_bank_account(self):
		if self.default_bank_account:
			is_company_account = frappe.db.get_value(
				"Bank Account", self.default_bank_account, "is_company_account"
			)
			if not is_company_account:
				frappe.throw(
					_("{0} is not a company bank account").format(frappe.bold(self.default_bank_account))
				)

	def validate_internal_customer(self):
		if not self.is_internal_customer:
			self.represents_company = ""

		internal_customer = frappe.db.get_value(
			"Customer",
			{
				"is_internal_customer": 1,
				"represents_company": self.represents_company,
				"name": ("!=", self.name),
			},
			"name",
		)

		if internal_customer:
			frappe.throw(
				_("Internal Customer for company {0} already exists").format(
					frappe.bold(self.represents_company)
				)
			)

	def on_update(self):
		self.validate_name_with_customer_group()
		self.create_primary_contact()
		self.create_primary_address()
		self.update_lead_status()

		if self.flags.is_new_doc:
			self.link_lead_address_and_contact()
			self.copy_communication()

		self.update_customer_groups()

	def add_role_for_user(self):
		for portal_user in self.portal_users:
			add_role_for_portal_user(portal_user, "Customer")

	def update_customer_groups(self):
		ignore_doctypes = ["Lead", "Opportunity", "POS Profile", "Tax Rule", "Pricing Rule"]
		if frappe.flags.customer_group_changed:
			update_linked_doctypes(
				"Customer", self.name, "Customer Group", self.customer_group, ignore_doctypes
			)

	def create_primary_contact(self):
		if not self.customer_primary_contact and not self.lead_name:
			if self.mobile_no or self.email_id:
				contact = make_contact(self)
				self.db_set("customer_primary_contact", contact.name)
				self.db_set("mobile_no", self.mobile_no)
				self.db_set("email_id", self.email_id)

	def create_primary_address(self):
		from frappe.contacts.doctype.address.address import get_address_display

		if self.flags.is_new_doc and self.get("address_line1"):
			address = make_address(self)
			address_display = get_address_display(address.name)

			self.db_set("customer_primary_address", address.name)
			self.db_set("primary_address", address_display)

	def update_lead_status(self):
		"""If Customer created from Lead, update lead status to "Converted"
		update Customer link in Quotation, Opportunity"""
		if self.lead_name:
			update_values = {"status": "Converted"}
			update_values["lead_stage"] = "Customer"
			frappe.db.set_value("Lead", self.lead_name, update_values)

	def link_lead_address_and_contact(self):
		if self.lead_name:
			# assign lead address and contact to customer (if already not set)
			linked_contacts_and_addresses = frappe.get_all(
				"Dynamic Link",
				filters=[
					["parenttype", "in", ["Contact", "Address"]],
					["link_doctype", "=", "Lead"],
					["link_name", "=", self.lead_name],
				],
				fields=["parent as name", "parenttype as doctype"],
			)

			for row in linked_contacts_and_addresses:
				linked_doc = frappe.get_doc(row.doctype, row.name)
				if not linked_doc.has_link("Customer", self.name):
					linked_doc.append("links", dict(link_doctype="Customer", link_name=self.name))
					linked_doc.save(ignore_permissions=self.flags.ignore_permissions)

	def copy_communication(self):
		if not self.lead_name or not frappe.db.get_single_value(
			"CRM Settings", "carry_forward_communication_and_comments"
		):
			return

		from erpnext.crm.utils import copy_comments, link_communications

		copy_comments("Lead", self.lead_name, self)
		link_communications("Lead", self.lead_name, self)

	def validate_name_with_customer_group(self):
		if frappe.db.exists("Customer Group", self.name):
			frappe.throw(
				_(
					"A Customer Group exists with same name please change the Customer name or rename the Customer Group"
				),
				frappe.NameError,
			)

	def validate_credit_limit_on_change(self):
		if self.get("__islocal") or not self.credit_limits:
			return

		past_credit_limits = [
			d.credit_limit
			for d in frappe.db.get_all(
				"Customer Credit Limit",
				filters={"parent": self.name},
				fields=["credit_limit"],
				order_by="company",
			)
		]

		current_credit_limits = [d.credit_limit for d in sorted(self.credit_limits, key=lambda k: k.company)]

		if past_credit_limits == current_credit_limits:
			return

		company_record = []
		for limit in self.credit_limits:
			if limit.company in company_record:
				frappe.throw(
					_("Credit limit is already defined for the Company {0}").format(limit.company, self.name)
				)
			else:
				company_record.append(limit.company)

			outstanding_amt = get_customer_outstanding(
				self.name, limit.company, ignore_outstanding_sales_order=limit.bypass_credit_limit_check
			)
			if flt(limit.credit_limit) < outstanding_amt:
				frappe.throw(
					_(
						"""New credit limit is less than current outstanding amount for the customer. Credit limit has to be atleast {0}"""
					).format(outstanding_amt)
				)

	def on_trash(self):
		if self.customer_primary_contact:
			self.db_set("customer_primary_contact", None)
		if self.customer_primary_address:
			self.db_set("customer_primary_address", None)

		delete_contact_and_address("Customer", self.name)
		if self.lead_name:
			frappe.db.sql("update `tabLead` set status='Interested' where name=%s", self.lead_name)

	def after_rename(self, olddn, newdn, merge=False):
		if frappe.defaults.get_global_default("cust_master_name") == "Customer Name":
			self.db_set("customer_name", newdn)

	def set_loyalty_program(self):
		if self.loyalty_program:
			return

		loyalty_program = get_loyalty_programs(self)
		if not loyalty_program:
			return

		if len(loyalty_program) == 1:
			self.loyalty_program = loyalty_program[0]
		else:
			frappe.msgprint(
				_("Multiple Loyalty Programs found for Customer {}. Please select manually.").format(
					frappe.bold(self.customer_name)
				)
			)

@deprecated
def create_contact(contact, party_type, party, email):
	"""Create contact based on given contact name"""
	first, middle, last = parse_full_name(contact)
	doc = frappe.get_doc(
		{
			"doctype": "Contact",
			"first_name": first,
			"middle_name": middle,
			"last_name": last,
			"is_primary_contact": 1,
		}
	)
	doc.append("email_ids", dict(email_id=email, is_primary=1))
	doc.append("links", dict(link_doctype=party_type, link_name=party))
	return doc.insert()


@frappe.whitelist()
def make_quotation(source_name, target_doc=None):
	def set_missing_values(source, target):
		_set_missing_values(source, target)

	target_doc = get_mapped_doc(
		"Customer",
		source_name,
		{"Customer": {"doctype": "Quotation", "field_map": {"name": "party_name"}}},
		target_doc,
		set_missing_values,
	)

	target_doc.quotation_to = "Customer"
	target_doc.run_method("set_missing_values")
	target_doc.run_method("set_other_charges")
	target_doc.run_method("calculate_taxes_and_totals")

	price_list, currency = frappe.db.get_value(
		"Customer", {"name": source_name}, ["default_price_list", "default_currency"]
	)
	if price_list:
		target_doc.selling_price_list = price_list
	if currency:
		target_doc.currency = currency

	return target_doc


@frappe.whitelist()
def make_opportunity(source_name, target_doc=None):
	def set_missing_values(source, target):
		_set_missing_values(source, target)

	target_doc = get_mapped_doc(
		"Customer",
		source_name,
		{
			"Customer": {
				"doctype": "Opportunity",
				"field_map": {
					"name": "party_name",
					"doctype": "opportunity_from",
				},
			}
		},
		target_doc,
		set_missing_values,
	)

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
def get_loyalty_programs(doc):
	"""returns applicable loyalty programs for a customer"""

	lp_details = []
	loyalty_programs = frappe.get_all(
		"Loyalty Program",
		fields=["name", "customer_group", "customer_territory"],
		filters={
			"auto_opt_in": 1,
			"from_date": ["<=", today()],
			"ifnull(to_date, '2500-01-01')": [">=", today()],
		},
	)

	for loyalty_program in loyalty_programs:
		if (
			not loyalty_program.customer_group
			or doc.customer_group
			in get_nested_links(
				"Customer Group", loyalty_program.customer_group, doc.flags.ignore_permissions
			)
		) and (
			not loyalty_program.customer_territory
			or doc.territory
			in get_nested_links("Territory", loyalty_program.customer_territory, doc.flags.ignore_permissions)
		):
			lp_details.append(loyalty_program.name)

	return lp_details


def get_nested_links(link_doctype, link_name, ignore_permissions=False):
	from frappe.desk.treeview import _get_children

	links = [link_name]
	for d in _get_children(link_doctype, link_name, ignore_permissions):
		links.append(d.value)

	return links


def check_credit_limit(customer, company, ignore_outstanding_sales_order=False, extra_amount=0):
	credit_limit = get_credit_limit(customer, company)
	if not credit_limit:
		return

	customer_outstanding = get_customer_outstanding(customer, company, ignore_outstanding_sales_order)
	if extra_amount > 0:
		customer_outstanding += flt(extra_amount)

	if credit_limit > 0 and flt(customer_outstanding) > credit_limit:
		message = _("Credit limit has been crossed for customer {0} ({1}/{2})").format(
			customer, customer_outstanding, credit_limit
		)

		message += "<br><br>"

		# If not authorized person raise exception
		credit_controller_role = frappe.db.get_single_value("Accounts Settings", "credit_controller")
		if not credit_controller_role or credit_controller_role not in frappe.get_roles():
			# form a list of emails for the credit controller users
			credit_controller_users = get_users_with_role(credit_controller_role or "Sales Master Manager")

			# form a list of emails and names to show to the user
			credit_controller_users_formatted = [
				get_formatted_email(user).replace("<", "(").replace(">", ")")
				for user in credit_controller_users
			]
			if not credit_controller_users_formatted:
				frappe.throw(
					_("Please contact your administrator to extend the credit limits for {0}.").format(
						customer
					)
				)

			user_list = "<br><br><ul><li>{}</li></ul>".format("<li>".join(credit_controller_users_formatted))

			message += _(
				"Please contact any of the following users to extend the credit limits for {0}: {1}"
			).format(customer, user_list)

			# if the current user does not have permissions to override credit limit,
			# prompt them to send out an email to the controller users
			frappe.msgprint(
				message,
				title=_("Credit Limit Crossed"),
				raise_exception=1,
				primary_action={
					"label": "Send Email",
					"server_action": "erpnext.selling.doctype.customer.customer.send_emails",
					"hide_on_success": True,
					"args": {
						"customer": customer,
						"customer_outstanding": customer_outstanding,
						"credit_limit": credit_limit,
						"credit_controller_users_list": credit_controller_users,
					},
				},
			)


@frappe.whitelist()
def send_emails(args):
	args = json.loads(args)
	subject = _("Credit limit reached for customer {0}").format(args.get("customer"))
	message = _("Credit limit has been crossed for customer {0} ({1}/{2})").format(
		args.get("customer"), args.get("customer_outstanding"), args.get("credit_limit")
	)
	frappe.sendmail(recipients=args.get("credit_controller_users_list"), subject=subject, message=message)


def get_customer_outstanding(customer, company, ignore_outstanding_sales_order=False, cost_center=None):
	# Outstanding based on GL Entries
	cond = ""
	if cost_center:
		lft, rgt = frappe.get_cached_value("Cost Center", cost_center, ["lft", "rgt"])

		cond = f""" and cost_center in (select name from `tabCost Center` where
			lft >= {lft} and rgt <= {rgt})"""

	outstanding_based_on_gle = frappe.db.sql(
		f"""
		select sum(debit) - sum(credit)
		from `tabGL Entry` where party_type = 'Customer'
		and is_cancelled = 0 and party = %s
		and company=%s {cond}""",
		(customer, company),
	)

	outstanding_based_on_gle = flt(outstanding_based_on_gle[0][0]) if outstanding_based_on_gle else 0

	# Outstanding based on Sales Order
	outstanding_based_on_so = 0

	# if credit limit check is bypassed at sales order level,
	# we should not consider outstanding Sales Orders, when customer credit balance report is run
	if not ignore_outstanding_sales_order:
		outstanding_based_on_so = frappe.db.sql(
			"""
			select sum(base_grand_total*(100 - per_billed)/100)
			from `tabSales Order`
			where customer=%s and docstatus = 1 and company=%s
			and per_billed < 100 and status != 'Closed'""",
			(customer, company),
		)

		outstanding_based_on_so = flt(outstanding_based_on_so[0][0]) if outstanding_based_on_so else 0

	# Outstanding based on Delivery Note, which are not created against Sales Order
	outstanding_based_on_dn = 0

	unmarked_delivery_note_items = frappe.db.sql(
		"""select
			dn_item.name, dn_item.amount, dn.base_net_total, dn.base_grand_total
		from `tabDelivery Note` dn, `tabDelivery Note Item` dn_item
		where
			dn.name = dn_item.parent
			and dn.customer=%s and dn.company=%s
			and dn.docstatus = 1 and dn.status not in ('Closed', 'Stopped')
			and ifnull(dn_item.against_sales_order, '') = ''
			and ifnull(dn_item.against_sales_invoice, '') = ''
		""",
		(customer, company),
		as_dict=True,
	)

	if not unmarked_delivery_note_items:
		return outstanding_based_on_gle + outstanding_based_on_so

	si_amounts = frappe.db.sql(
		"""
		SELECT
			dn_detail, sum(amount) from `tabSales Invoice Item`
		WHERE
			docstatus = 1
			and dn_detail in ({})
		GROUP BY dn_detail""".format(
			", ".join(frappe.db.escape(dn_item.name) for dn_item in unmarked_delivery_note_items)
		)
	)

	si_amounts = {si_item[0]: si_item[1] for si_item in si_amounts}

	for dn_item in unmarked_delivery_note_items:
		dn_amount = flt(dn_item.amount)
		si_amount = flt(si_amounts.get(dn_item.name))

		if dn_amount > si_amount and dn_item.base_net_total:
			outstanding_based_on_dn += (
				(dn_amount - si_amount) / dn_item.base_net_total
			) * dn_item.base_grand_total

	return outstanding_based_on_gle + outstanding_based_on_so + outstanding_based_on_dn


def get_credit_limit(customer, company):
	credit_limit = None

	if customer:
		credit_limit = frappe.db.get_value(
			"Customer Credit Limit",
			{"parent": customer, "parenttype": "Customer", "company": company},
			"credit_limit",
		)

		if not credit_limit:
			customer_group = frappe.get_cached_value("Customer", customer, "customer_group")

			result = frappe.db.get_values(
				"Customer Credit Limit",
				{"parent": customer_group, "parenttype": "Customer Group", "company": company},
				fieldname=["credit_limit", "bypass_credit_limit_check"],
				as_dict=True,
			)
			if result and not result[0].bypass_credit_limit_check:
				credit_limit = result[0].credit_limit

	if not credit_limit:
		credit_limit = frappe.get_cached_value("Company", company, "credit_limit")

	return flt(credit_limit)


def make_contact(args, is_primary_contact=1):
	values = {
		"doctype": "Contact",
		"is_primary_contact": is_primary_contact,
		"links": [{"link_doctype": args.get("doctype"), "link_name": args.get("name")}],
	}

	party_type = args.customer_type if args.doctype == "Customer" else args.supplier_type
	party_name_key = "customer_name" if args.doctype == "Customer" else "supplier_name"

	if party_type == "Individual":
		first, middle, last = parse_full_name(args.get(party_name_key))
		values.update(
			{
				"first_name": first,
				"middle_name": middle,
				"last_name": last,
			}
		)
	else:
		values.update(
			{
				"company_name": args.get(party_name_key),
			}
		)

	contact = frappe.get_doc(values)

	if args.get("email_id"):
		contact.add_email(args.get("email_id"), is_primary=True)
	if args.get("mobile_no"):
		contact.add_phone(args.get("mobile_no"), is_primary_mobile_no=True)

	if flags := args.get("flags"):
		contact.insert(ignore_permissions=flags.get("ignore_permissions"))
	else:
		contact.insert()

	return contact


def make_address(args, is_primary_address=1, is_shipping_address=1):
	reqd_fields = []
	for field in ["city", "country"]:
		if not args.get(field):
			reqd_fields.append("<li>" + field.title() + "</li>")

	if reqd_fields:
		msg = _("Following fields are mandatory to create address:")
		frappe.throw(
			"{} <br><br> <ul>{}</ul>".format(msg, "\n".join(reqd_fields)),
			title=_("Missing Values Required"),
		)

	party_name_key = "customer_name" if args.doctype == "Customer" else "supplier_name"

	address = frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": args.get(party_name_key),
			"address_name": args.get(party_name_key),
			"address_line1": args.get("address_line1"),
			"address_line2": args.get("address_line2"),
			"city": args.get("city"),
			"state": args.get("state"),
			"pincode": args.get("pincode"),
			"country": args.get("country"),
			"is_primary_address": is_primary_address,
			"is_shipping_address": is_shipping_address,
			"links": [{"link_doctype": args.get("doctype"), "link_name": args.get("name")}],
		}
	)

	if flags := args.get("flags"):
		address.insert(ignore_permissions=flags.get("ignore_permissions"))
	else:
		address.insert()

	return address


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_customer_primary_contact(doctype, txt, searchfield, start, page_len, filters):
	customer = filters.get("customer")

	con = qb.DocType("Contact")
	dlink = qb.DocType("Dynamic Link")

	return (
		qb.from_(con)
		.join(dlink)
		.on(con.name == dlink.parent)
		.select(con.name, con.email_id)
		.where((dlink.link_name == customer) & (con.name.like(f"%{txt}%")))
		.run()
	)


def parse_full_name(full_name: str) -> tuple[str, str | None, str | None]:
	"""Parse full name into first name, middle name and last name"""
	names = full_name.split()
	first_name = names[0]
	middle_name = " ".join(names[1:-1]) if len(names) > 2 else None
	last_name = names[-1] if len(names) > 1 else None

	return first_name, middle_name, last_name

@frappe.whitelist()
def update_customer_priority_data(customer_name, haravan_id):
	"""Background job: Fetch and update priority data for a single customer"""
	url = f"{config.PRIORITY_BASE_URL}/user/priority/{haravan_id}/haravan"
	response = requests.get(url, timeout=10)

	if response.status_code != 200:
		frappe.log_error(
			f"Priority API failed for customer {customer_name} (haravan_id: {haravan_id})",
			"Priority API Error"
		)
		return

	data = response.json()

	# Calculate actual_cumulative_revenue from ERP Sales Orders (our source of truth)
	actual_revenue = frappe.db.sql("""
		SELECT SUM(grand_total) as total
		FROM `tabSales Order`
		WHERE customer = %s
		AND financial_status IN ('Paid', 'Partially Paid')
		AND cancelled_status = 'Uncancelled'
	""", (customer_name,), as_dict=True)[0].total or 0

	# Extract point data from Priority API (referral revenue now comes from coupons)
	withdraw_point = data.get("withdrawPoint", 0)
	available_point = data.get("pointAvailable", 0)
	withdraw_cash_amount = data.get("withdrawCashAmount", 0)
	withdraw_cash_pending = data.get("pendingCashback", 0)
	total_referral_point = data.get("totalPoint", 0)
	partner_role = data.get("role", "")  # Get role from Priority API (staff, partnerA, partnerB, etc.)

	# Update customer fields (referral_cumulative_revenue removed - now calculated from coupons)
	frappe.db.sql("""
		UPDATE `tabCustomer`
		SET
			actual_cumulative_revenue = %s,
			withdraw_point = %s,
			available_point_amount = %s,
			withdraw_cash_amount = %s,
			withdraw_cash_amount_pending = %s,
			total_referral_point = %s,
			partner_role = %s
		WHERE name = %s
	""", (actual_revenue, withdraw_point, available_point, withdraw_cash_amount,
			withdraw_cash_pending, total_referral_point, partner_role, customer_name))

	frappe.db.commit()

	evaluate_and_update_customer_rank(customer_name)

@frappe.whitelist()
def reevaluate_customer_rank(customer_name):
	try:
		customer = frappe.get_doc("Customer", customer_name)

		if not customer.haravan_id:
			frappe.throw("Customer must have a Haravan ID to evaluate rank")

		frappe.db.set_value("Customer", customer_name, {
			"rank": None,
			"rank_updated_at": None
		})
		frappe.db.commit()

		update_customers_coupons(customer.name, customer.haravan_id)
		load_buyback_records_async(customer.name)
		update_customer_priority_data(customer.name, customer.haravan_id)

		frappe.msgprint(f"Successfully reevaluated rank for {customer.customer_name}")

	except Exception as e:
		frappe.log_error(
			f"Error reevaluating rank for {customer_name}: {str(e)}",
			"Customer Rank Re-evaluation Error"
		)
		frappe.throw(f"Failed to reevaluate customer rank: {str(e)}")

@frappe.whitelist()
def bulk_reevaluate_customer_rank(customer_names):
	"""Bulk re-evaluate rank for multiple customers from list view"""
	import json

	if isinstance(customer_names, str):
		customer_names = json.loads(customer_names)
	success_count = 0
	failed_count = 0

	for customer_name in customer_names:
		try:
			customer = frappe.get_doc("Customer", customer_name)

			if not customer.haravan_id:
				failed_count += 1
				continue

			frappe.db.set_value("Customer", customer_name, {
				"rank": None,
				"rank_updated_at": None
			})
			frappe.db.commit()

			update_customers_coupons(customer.name, customer.haravan_id)
			load_buyback_records_async(customer.name)
			update_customer_priority_data(customer.name, customer.haravan_id)

			success_count += 1

		except Exception as e:
			frappe.log_error(
				f"Error re-evaluating rank for {customer_name}: {str(e)}",
				"Bulk Rank Re-evaluation Error"
			)
			failed_count += 1

	return {
		"success": success_count,
		"failed": failed_count
	}


def evaluate_and_update_customer_rank(customer_name, auto_commit=True):
	"""
	Historical replay approach for accurate rank evaluation:
	- Phase 1: Initialize rank_updated_at if NULL
	- Phase 2: Replay all orders chronologically for upgrades
	- Phase 3: Check 12-month downgrades
	"""
	customer = frappe.get_doc("Customer", customer_name)

	if not customer.rank_updated_at:
		_initialize_customer_rank(customer_name, auto_commit)
		customer.reload()

	_replay_rank_upgrades(customer_name, auto_commit)
	customer.reload()

	_check_12_month_downgrades(customer_name, auto_commit)

	# Update total_cumulative_revenue
	_update_total_cumulative_revenue(customer_name, auto_commit)

	# Update current 12-month score
	_update_current_12_month_score(customer_name, auto_commit)

def evaluate_all_customer_ranks():
	"""
	Scheduled job: Evaluate and update ranks for all customers
	Runs every 15 minute via cron
	"""

	customers = frappe.db.sql("""
		SELECT c.name, c.haravan_id, c.rank_updated_at, c.rank, c.total_cumulative_revenue
		FROM `tabCustomer` c
		WHERE c.haravan_id IS NOT NULL
		AND (
			EXISTS (
				SELECT 1 FROM `tabSales Order` so
				WHERE so.customer = c.name
				AND so.cancelled_status = 'Uncancelled'
				AND so.financial_status in ('Paid', 'Partially Paid')
				AND so.total_amount != 0
			)
			OR EXISTS (
				SELECT 1 FROM `tabCoupon` cp
				WHERE cp.parent = c.name
			)
		)
		ORDER BY c.rank_updated_at DESC
		LIMIT 200
	""", as_dict=True)

	for customer in customers:
		try:
			update_customers_coupons(customer.name, customer.haravan_id)
			load_buyback_records_async(customer.name)
			update_customer_priority_data(customer.name, customer.haravan_id)
		except Exception as e:
			frappe.log_error(
				f"Error updating priority data for {customer.name}: {str(e)}",
				"Priority Data Update Error"
			)

def _get_first_paid_order_date(customer_name):
	"""
	Get the date of the first paid order for a customer
	Returns the transaction_date of the first order with payment
	Criteria: financial_status IN ('Paid', 'Partially Paid') AND cancelled_status = 'Uncancelled'
	Excludes: Pending, Refunded, Partially Refunded
	"""
	first_order = frappe.db.sql("""
		SELECT transaction_date
		FROM `tabSales Order`
		WHERE customer = %s
		AND financial_status IN ('Paid', 'Partially Paid')
		AND cancelled_status = 'Uncancelled'
		ORDER BY transaction_date ASC
		LIMIT 1
	""", (customer_name,), as_dict=True)

	if first_order:
		return getdate(first_order[0].transaction_date)
	return None

def _get_first_coupon_date(customer_name):
	"""
	Get the date of the first coupon for a customer
	Returns the end_date of the first coupon (when referral was earned)
	Falls back to start_date if end_date is NULL
	"""
	first_coupon = frappe.db.sql("""
		SELECT COALESCE(end_date, start_date) as coupon_date
		FROM `tabCoupon`
		WHERE parent = %s
		AND payment_status IN ('Paid', 'Pending')
		ORDER BY COALESCE(end_date, start_date) ASC
		LIMIT 1
	""", (customer_name,), as_dict=True)

	if first_coupon:
		return getdate(first_coupon[0].coupon_date)
	return None

def _determine_rank_from_cumulative(revenue, referral_revenue):
	"""Determine rank based on cumulative revenue"""
	if revenue == 0:
		return CustomerRank.NO_RANK

	has_referral = referral_revenue > 0

	if has_referral:
		if revenue >= RankThreshold.PLATINUM_WITH_REFERRAL:
			return CustomerRank.PLATINUM
		if revenue >= RankThreshold.GOLD_WITH_REFERRAL:
			return CustomerRank.GOLD
	else:
		if revenue >= RankThreshold.PLATINUM_PURCHASE:
			return CustomerRank.PLATINUM
		if revenue >= RankThreshold.GOLD_PURCHASE:
			return CustomerRank.GOLD

	return CustomerRank.SILVER

def _calculate_12_month_score(customer_name, rank_updated_at):
	"""Calculate purchasing activity in the 12 months since rank_updated_at
	Only counts orders (grand_total), no buyback subtraction"""
	start_date = getdate(rank_updated_at)
	end_date = add_months(start_date, 12)

	sales_orders = frappe.db.sql("""
		SELECT SUM(grand_total) as total
		FROM `tabSales Order`
		WHERE customer = %s
		AND financial_status IN ('Paid', 'Partially Paid')
		AND cancelled_status = 'Uncancelled'
		AND transaction_date > %s
		AND transaction_date < %s
	""", (customer_name, start_date, end_date), as_dict=True)

	actual_revenue = flt(sales_orders[0].total if sales_orders else 0)

	# For rank evaluation, only count purchasing activity (no buyback subtraction)
	return actual_revenue

def _get_referral_revenue_in_12_month_period(customer_name, rank_updated_at):
	"""Get referral revenue earned in the 12-month period after rank_updated_at
	Uses coupon end_date (or start_date if NULL) to determine when referral was earned"""
	start_date = getdate(rank_updated_at)
	end_date = add_months(start_date, 12)

	referral_revenue = frappe.db.sql("""
		SELECT SUM(total_price) as total
		FROM `tabCoupon`
		WHERE parent = %s
		AND DATE(COALESCE(end_date, start_date)) > %s
		AND DATE(COALESCE(end_date, start_date)) < %s
		AND payment_status IN ('Paid', 'Pending')
	""", (customer_name, start_date, end_date), as_dict=True)

	return flt(referral_revenue[0].total if referral_revenue else 0)

def _get_buyback_revenue_in_period(customer_name, start_date, end_date):
	"""
	Get buyback revenue for a specific period from Larksuite API
	"""
	from frappe.utils import formatdate

	customer = frappe.get_doc("Customer", customer_name)
	phone_number = customer.phone or customer.mobile_no
	if not phone_number:
		return 0

	try:
		response = requests.get(
			url=f"{config.FN_BASE_URL}/api/larksuites/buyback-exchanges",
			params={
				"phone_number": phone_number,
				"submitted_date_start": formatdate(start_date, "yyyy-MM-dd"),
				"submitted_date_end": formatdate(end_date, "yyyy-MM-dd")
			},
			headers={"Authorization": f"Bearer {config.FN_BEARER_TOKEN}"},
			timeout=10
		)

		if response.status_code == 200:
			data = response.json()
			if data.get("sucess"):  # Note: API has typo "sucess"
				records = data.get("data", [])
				# Sum up all buyback amounts in the period
				total_buyback = sum(flt(record.get("refund_amount", 0)) for record in records)
				return total_buyback

		return 0

	except Exception as e:
		frappe.log_error(
			f"Error fetching buyback revenue for {customer_name} ({start_date} to {end_date}): {str(e)}",
			"Buyback Revenue Calculation Error"
		)
		return 0

def _is_rank_higher(rank1, rank2):
	"""Check if rank1 is higher than rank2"""
	return RANK_ORDER.get(rank1, 0) > RANK_ORDER.get(rank2, 0)

def _is_rank_lower(rank1, rank2):
	"""Check if rank1 is lower than rank2"""
	return RANK_ORDER.get(rank1, 0) < RANK_ORDER.get(rank2, 0)

def _downgrade_one_level(current_rank):
	"""Downgrade rank by one level (Silver is minimum - cannot downgrade below Silver)"""
	if current_rank == CustomerRank.PLATINUM:
		return CustomerRank.GOLD
	elif current_rank == CustomerRank.GOLD:
		return CustomerRank.SILVER
	elif current_rank == CustomerRank.SILVER:
		return CustomerRank.SILVER  # Cannot downgrade below Silver
	return CustomerRank.NO_RANK

def update_all_customers_revenue():

    payload = {}  # Add any required payload if needed
    response = requests.get(f"{config.PRIORITY_BASE_URL}/user/priority/get-all", json=payload)

    if response.status_code != 200:
        frappe.throw("Failed to fetch data from priority API")

    results = response.json().get("results", [])

    for result in results:
        haravan_id = result.get("haravanId")
        referrals_revenue = result.get("totalReferAmount", 0)
        withdraw_cashback = result.get("withdrawAmount", 0)
        pending_cashback = result.get("remainingCashBack", 0)
        cashback = withdraw_cashback + pending_cashback

        # Update tabCustomer table based on haravanId
        frappe.db.sql("""
            UPDATE `tabCustomer`
            SET
                referrals_revenue = %s,
                cashback = %s,
                withdraw_cashback = %s,
                pending_cashback = %s
            WHERE haravan_id = %s
        """, (referrals_revenue, cashback, withdraw_cashback, pending_cashback, str(haravan_id)))

@frappe.whitelist()
def load_buyback_records_async(customer):
	"""Async method to load buyback records after page load"""
	customer_doc = frappe.get_doc("Customer", customer)
	phone_number = customer_doc.phone or customer_doc.mobile_no
	if not phone_number:
		return []

	try:
		response = requests.get(
			url=f"{config.FN_BASE_URL}/api/larksuites/buyback-exchanges",
			params={"phone_number": phone_number},
			headers={"Authorization": f"Bearer {config.FN_BEARER_TOKEN}"},
			timeout=3
		)

		if response.status_code == 200:
			data = response.json()
			if data.get("sucess"):  # Note: API has typo "sucess"
				records = data.get("data", [])
				# Calculate total buyback revenue and save it (only if different from current)
				total_buyback = sum(flt(record.get("refund_amount", 0)) for record in records)
				current_buyback = flt(customer_doc.buyback_revenue or 0)
				if total_buyback != current_buyback:
					frappe.db.set_value("Customer", customer, "buyback_revenue", total_buyback)
					frappe.db.commit()
				return records
	except:
		pass  # Silently fail

	return []

def _initialize_customer_rank(customer_name, auto_commit=True):
	"""Phase 1: Initialize rank_updated_at and initial rank
	Uses whichever came first: first order or first coupon"""
	customer = frappe.get_doc("Customer", customer_name)

	first_order_date = _get_first_paid_order_date(customer_name)
	first_coupon_date = _get_first_coupon_date(customer_name)

	if not first_order_date and not first_coupon_date:
		creation_date = getdate(customer.creation)
		customer.db_set("rank", CustomerRank.NO_RANK, update_modified=True)
		customer.db_set("rank_updated_at", creation_date, update_modified=True)

		if auto_commit:
			frappe.db.commit()
		return

	if first_order_date and first_coupon_date:
		first_activity_date = min(first_order_date, first_coupon_date)
	elif first_order_date:
		first_activity_date = first_order_date
	else:
		first_activity_date = first_coupon_date

	customer.db_set("rank_updated_at", first_activity_date, update_modified=True)
	cumulative_at_first = _get_cumulative_revenue_at_date(customer_name, first_activity_date)
	referral_at_first = _get_referral_revenue_up_to_date(customer_name, first_activity_date)
	initial_rank = _determine_rank_from_cumulative(cumulative_at_first, referral_at_first)

	customer.db_set("rank", initial_rank, update_modified=True)

	if auto_commit:
		frappe.db.commit()

def _replay_rank_upgrades(customer_name, auto_commit=True):
	"""Phase 2: Replay all orders AND coupons chronologically to find upgrade points"""
	customer = frappe.get_doc("Customer", customer_name)
	current_rank_updated_at = customer.rank_updated_at
	current_rank = customer.rank
	events = []

	orders = frappe.db.sql("""
		SELECT transaction_date as event_date
		FROM `tabSales Order`
		WHERE customer = %s
		AND financial_status IN ('Paid', 'Partially Paid')
		AND cancelled_status = 'Uncancelled'
		AND transaction_date > %s
	""", (customer_name, current_rank_updated_at), as_dict=True)

	for order in orders:
		events.append(getdate(order.event_date))

	coupons = frappe.db.sql("""
		SELECT DATE(COALESCE(end_date, start_date)) as event_date
		FROM `tabCoupon`
		WHERE parent = %s
		AND COALESCE(end_date, start_date) > %s
		AND payment_status IN ('Paid', 'Pending')
	""", (customer_name, current_rank_updated_at), as_dict=True)

	for coupon in coupons:
		events.append(getdate(coupon.event_date))

	if not events:
		return

	unique_events = sorted(set(events))

	for event_date in unique_events:
		cumulative_at_date = _get_cumulative_revenue_at_date(customer_name, event_date)
		referral_at_date = _get_referral_revenue_up_to_date(customer_name, event_date)
		qualified_rank = _determine_rank_from_cumulative(cumulative_at_date, referral_at_date)

		if _is_rank_higher(qualified_rank, current_rank):
			customer.db_set("rank", qualified_rank, update_modified=True)
			customer.db_set("rank_updated_at", event_date, update_modified=True)
			customer.db_set("rank_score_12m", 0, update_modified=True)

			if auto_commit:
				frappe.db.commit()

			frappe.logger().info(f"Upgraded {customer_name} from {current_rank} to {qualified_rank} on {event_date} (cumulative: {cumulative_at_date:,.2f})")

			current_rank = qualified_rank
			current_rank_updated_at = event_date

def _check_12_month_downgrades(customer_name, auto_commit=True):
	"""Phase 3: Check if 12-month downgrade evaluation is needed"""
	customer = frappe.get_doc("Customer", customer_name)
	rank_updated_at = customer.rank_updated_at
	current_rank = customer.rank

	if not rank_updated_at:
		return

	partner_role = (getattr(customer, 'partner_role', '') or '').lower()
	is_protected = partner_role in ["staff", "partnerA", "partnerB"]

	today = getdate(nowdate())
	next_evaluation_date = add_months(rank_updated_at, 12)

	while today >= next_evaluation_date:
		orders_12m = _calculate_12_month_score(customer_name, rank_updated_at)
		referral_12m = _get_referral_revenue_in_12_month_period(customer_name, rank_updated_at)
		rank_score_12m = orders_12m + referral_12m

		qualified_rank = _determine_rank_from_cumulative(rank_score_12m, referral_12m)

		if _is_rank_lower(qualified_rank, current_rank):
			downgraded_rank = _downgrade_one_level(current_rank)

			if not is_protected and current_rank != CustomerRank.SILVER:
				customer.db_set("rank", downgraded_rank, update_modified=True)
				frappe.logger().info(f"Downgraded {customer_name} from {current_rank} to {downgraded_rank} (12m score: {rank_score_12m})")
				current_rank = downgraded_rank
			elif is_protected:
				frappe.logger().info(f"Protected role {partner_role}: Skipped downgrade for {customer_name} (12m score: {rank_score_12m})")
			else:
				frappe.logger().info(f"Already at Silver: No downgrade for {customer_name} (12m score: {rank_score_12m})")

			customer.db_set("rank_updated_at", next_evaluation_date, update_modified=True)
			customer.db_set("rank_score_12m", rank_score_12m, update_modified=True)

			if auto_commit:
				frappe.db.commit()

			rank_updated_at = next_evaluation_date
			next_evaluation_date = add_months(rank_updated_at, 12)
		else:
			customer.db_set("rank_updated_at", next_evaluation_date, update_modified=True)
			customer.db_set("rank_score_12m", rank_score_12m, update_modified=True)

			if auto_commit:
				frappe.db.commit()

			rank_updated_at = next_evaluation_date
			next_evaluation_date = add_months(rank_updated_at, 12)

def _get_cumulative_revenue_at_date(customer_name, target_date):
	"""Calculate cumulative revenue up to a specific date (including that date)"""
	# Get actual revenue from sales orders up to target_date
	actual_revenue = frappe.db.sql("""
		SELECT SUM(grand_total) as total
		FROM `tabSales Order`
		WHERE customer = %s
		AND financial_status IN ('Paid', 'Partially Paid')
		AND cancelled_status = 'Uncancelled'
		AND transaction_date <= %s
	""", (customer_name, target_date), as_dict=True)[0].total or 0

	# Get referral revenue from coupons up to target_date (using end_date)
	referral_revenue = _get_referral_revenue_up_to_date(customer_name, target_date)

	# For historical replay, use gross revenue (no buyback subtraction)
	# Buybacks are only considered in 12-month evaluations, not for upgrade qualifications
	return flt(actual_revenue) + flt(referral_revenue)

def _get_cumulative_revenue_in_period(customer_name, start_date, end_date):
	"""Calculate cumulative revenue in a specific period (from start_date to end_date, inclusive)"""
	actual_revenue = frappe.db.sql("""
		SELECT SUM(grand_total) as total
		FROM `tabSales Order`
		WHERE customer = %s
		AND financial_status IN ('Paid', 'Partially Paid')
		AND cancelled_status = 'Uncancelled'
		AND transaction_date > %s
		AND transaction_date <= %s
	""", (customer_name, start_date, end_date), as_dict=True)[0].total or 0

	referral_revenue = _get_referral_revenue_in_period(customer_name, start_date, end_date)
	return flt(actual_revenue) + flt(referral_revenue)

def _get_referral_revenue_in_period(customer_name, start_date, end_date):
	"""Get referral revenue from coupons in a specific period (using end_date or start_date if NULL)"""
	referral_revenue = frappe.db.sql("""
		SELECT SUM(total_price) as total
		FROM `tabCoupon`
		WHERE parent = %s
		AND DATE(COALESCE(end_date, start_date)) > %s
		AND DATE(COALESCE(end_date, start_date)) <= %s
		AND payment_status IN ('Paid', 'Pending')
	""", (customer_name, start_date, end_date), as_dict=True)
	return flt(referral_revenue[0].total if referral_revenue else 0)

def _get_referral_revenue_up_to_date(customer_name, target_date):
	"""Get referral revenue from coupons up to a specific date (using end_date or start_date if NULL)"""
	referral_revenue = frappe.db.sql("""
		SELECT SUM(total_price) as total
		FROM `tabCoupon`
		WHERE parent = %s
		AND DATE(COALESCE(end_date, start_date)) <= %s
		AND payment_status IN ('Paid', 'Pending')
	""", (customer_name, target_date), as_dict=True)

	return flt(referral_revenue[0].total if referral_revenue else 0)

def _get_buyback_revenue_up_to_date(customer_name, target_date):
	"""Get total buyback revenue up to a specific date"""
	customer = frappe.get_doc("Customer", customer_name)
	phone_number = customer.phone or customer.mobile_no
	if not phone_number:
		return 0

	try:
		from frappe.utils import formatdate

		response = requests.get(
			url=f"{config.FN_BASE_URL}/api/larksuites/buyback-exchanges",
			params={
				"phone_number": phone_number,
				"submitted_date_end": formatdate(target_date, "yyyy-MM-dd")
			},
			headers={"Authorization": f"Bearer {config.FN_BEARER_TOKEN}"},
			timeout=10
		)

		if response.status_code == 200:
			data = response.json()
			if data.get("sucess"):  # Note: API has typo "sucess"
				records = data.get("data", [])
				total_buyback = sum(flt(record.get("refund_amount", 0)) for record in records)
				return total_buyback

		return 0

	except Exception as e:
		frappe.log_error(
			f"Error fetching buyback revenue up to {target_date} for {customer_name}: {str(e)}",
			"Buyback Revenue Calculation Error"
		)
		return 0

def _update_total_cumulative_revenue(customer_name, auto_commit=True):
	"""Update the total_cumulative_revenue field
	"""
	_update_referral_revenue_from_coupons(customer_name)
	customer = frappe.get_doc("Customer", customer_name)

	actual_revenue = flt(customer.get("actual_cumulative_revenue", 0))
	referral_revenue = flt(customer.get("referral_cumulative_revenue", 0))
	buyback_revenue = flt(customer.get("buyback_revenue", 0))

	total_cumulative = actual_revenue + referral_revenue - buyback_revenue
	if total_cumulative < 0:
		total_cumulative = 0

	customer.db_set("total_cumulative_revenue", total_cumulative, update_modified=True)

	if auto_commit:
		frappe.db.commit()


def _update_referral_revenue_from_coupons(customer_name):
	"""Calculate referral_cumulative_revenue from sum of coupon total_price"""
	total_referral = frappe.db.sql("""
		SELECT SUM(total_price) as total
		FROM `tabCoupon`
		WHERE parent = %s
		AND payment_status in ('Paid', 'Pending')
	""", (customer_name,), as_dict=True)[0].total or 0

	frappe.db.set_value("Customer", customer_name, "referral_cumulative_revenue", total_referral)
	frappe.db.commit()


def _update_current_12_month_score(customer_name, auto_commit=True):
	customer = frappe.get_doc("Customer", customer_name)

	if not customer.rank_updated_at:
		return

	# Calculate score from rank_updated_at to now (orders only)
	orders_12m = _calculate_12_month_score(customer_name, customer.rank_updated_at)

	customer.db_set("rank_score_12m", orders_12m, update_modified=True)

	if auto_commit:
		frappe.db.commit()
