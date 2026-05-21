# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import copy
import json
from typing import Literal

import frappe
import frappe.utils
import requests
from frappe import _, qb
from frappe.contacts.doctype.address.address import get_company_address
from frappe.desk.notifications import clear_doctype_notifications
from frappe.model.docstatus import DocStatus
from frappe.model.mapper import get_mapped_doc
from frappe.model.utils import get_fetch_values
from frappe.query_builder.functions import Sum
from frappe.utils import add_days, cint, cstr, flt, get_link_to_form, getdate, nowdate, parse_json, strip_html, add_to_date, get_datetime

from erpnext.accounts.doctype.sales_invoice.sales_invoice import (
	unlink_inter_company_doc,
	update_linked_doc,
	validate_inter_company_party,
)
from erpnext.accounts.party import get_party_account
from erpnext.config.config import config
from erpnext.controllers.selling_controller import SellingController
from erpnext.manufacturing.doctype.blanket_order.blanket_order import (
	validate_against_blanket_order,
)
from erpnext.manufacturing.doctype.production_plan.production_plan import (
	get_items_for_material_requests,
)
from erpnext.selling.doctype.customer.customer import check_credit_limit, reevaluate_customer_rank
from erpnext.setup.doctype.item_group.item_group import get_item_group_defaults
from erpnext.stock.doctype.item.item import get_item_defaults
from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import (
	get_sre_reserved_qty_details_for_voucher,
	has_reserved_stock,
)
from erpnext.stock.get_item_details import (
	ItemDetailsCtx,
	get_bin_details,
	get_default_bom,
	get_price_list_rate,
)
from erpnext.stock.stock_balance import get_reserved_qty, update_bin_qty

form_grid_templates = {"items": "templates/form_grid/item_grid.html"}


class WarehouseRequired(frappe.ValidationError):
	pass


class SalesOrder(SellingController):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.accounts.doctype.item_wise_tax_detail.item_wise_tax_detail import ItemWiseTaxDetail
		from erpnext.accounts.doctype.payment_entry_reference.payment_entry_reference import PaymentEntryReference
		from erpnext.accounts.doctype.payment_schedule.payment_schedule import PaymentSchedule
		from erpnext.accounts.doctype.pricing_rule_detail.pricing_rule_detail import PricingRuleDetail
		from erpnext.accounts.doctype.sales_taxes_and_charges.sales_taxes_and_charges import (
			SalesTaxesandCharges,
		)
		from erpnext.selling.doctype.order_and_debt_tracking.order_and_debt_tracking import (
			OrderandDebtTracking,
		)
		from erpnext.selling.doctype.sales_order_item.sales_order_item import SalesOrderItem
		from erpnext.selling.doctype.sales_order_payment_record.sales_order_payment_record import (
			SalesOrderPaymentRecord,
		)
		from erpnext.selling.doctype.sales_order_policy.sales_order_policy import SalesOrderPolicy
		from erpnext.selling.doctype.sales_order_product_category.sales_order_product_category import (
			SalesOrderProductCategory,
		)
		from erpnext.selling.doctype.sales_order_promotion.sales_order_promotion import SalesOrderPromotion
		from erpnext.selling.doctype.sales_order_purpose.sales_order_purpose import SalesOrderPurpose
		from erpnext.selling.doctype.sales_order_reference.sales_order_reference import SalesOrderReference
		from erpnext.selling.doctype.sales_team.sales_team import SalesTeam
		from erpnext.stock.doctype.packed_item.packed_item import PackedItem

		additional_discount_percentage: DF.Float
		address_display: DF.TextEditor | None
		advance_paid: DF.Currency
		amended_from: DF.Link | None
		amount_eligible_for_commission: DF.Currency
		apply_discount_on: DF.Literal["", "Grand Total", "Net Total"]
		auto_repeat: DF.Link | None
		balance: DF.Currency
		balance_group_payment: DF.Currency
		base_discount_amount: DF.Currency
		base_grand_total: DF.Currency
		base_in_words: DF.Data | None
		base_net_total: DF.Currency
		base_rounded_total: DF.Currency
		base_rounding_adjustment: DF.Currency
		base_total: DF.Currency
		base_total_taxes_and_charges: DF.Currency
		billing_address: DF.Literal["", "72 Nguy\u1ec5n C\u01b0 Trinh, Ph\u01b0\u1eddng B\u1ebfn Th\u00e0nh, TP H\u1ed3 Ch\u00ed Minh", "63 Kim M\u00e3, Ph\u01b0\u1eddng Gi\u1ea3ng V\u00f5, TP H\u00e0 N\u1ed9i", "209 \u0110\u01b0\u1eddng 30 Th\u00e1ng 4, Ph\u01b0\u1eddng Ninh Ki\u1ec1u, TP C\u1ea7n Th\u01a1"]
		billing_status: DF.Literal["Not Billed", "Fully Billed", "Partly Billed", "Closed"]
		birth_date: DF.Date | None
		campaign: DF.Link | None
		cancelled_status: DF.Literal["", "Uncancelled", "Cancelled"]
		carrier_status: DF.Literal["", "Not Delivered", "Ready To Pick", "Delivering", "Delivered"]
		commission_base_amount: DF.Currency
		commission_rate: DF.Float
		company: DF.Link
		company_address: DF.Link | None
		company_address_display: DF.TextEditor | None
		company_contact_person: DF.Link | None
		consultation_date: DF.Date | None
		contact_display: DF.SmallText | None
		contact_email: DF.Data | None
		contact_mobile: DF.SmallText | None
		contact_person: DF.Link | None
		contact_phone: DF.Data | None
		conversion_rate: DF.Float
		cost_center: DF.Link | None
		coupon_code: DF.Link | None
		currency: DF.Link
		customer: DF.Link
		customer_address: DF.Link | None
		customer_group: DF.Link | None
		customer_name: DF.Data | None
		customer_passport_id: DF.Data | None
		customer_personal_id: DF.Data | None
		customer_type: DF.Literal["", "New Customer", "Returning Customer"]
		date_of_issuance: DF.Date | None
		debt_history: DF.Table[OrderandDebtTracking]
		delivery_date: DF.Date | None
		delivery_location: DF.Literal["", "209, \u0110 30 th\u00e1ng 4, Xu\u00e2n Kh\u00e1nh, Ninh Ki\u1ec1u, C\u1ea7n Th\u01a1", "63 Kim M\u00e3, Qu\u1eadn Ba \u0110\u00ecnh, H\u00e0 N\u1ed9i", "72 Nguy\u1ec5n C\u01b0 Trinh, Qu\u1eadn 1, Th\u00e0nh Ph\u1ed1 H\u1ed3 Ch\u00ed Minh", "Giao v\u1ec1 \u0111\u1ecba ch\u1ec9 kh\u00e1ch"]
		delivery_status: DF.Literal["Not Delivered", "Fully Delivered", "Partially Delivered", "Closed", "Not Applicable"]
		deposit_amount: DF.Currency
		deposit_in_words: DF.SmallText | None
		deposit_location: DF.Link | None
		deposit_method: DF.Literal["", "Cash", "Bank Transfer", "Card"]
		disable_rounded_total: DF.Check
		discount_amount: DF.Currency
		dispatch_address: DF.TextEditor | None
		dispatch_address_name: DF.Link | None
		expected_delivery_date: DF.Date | None
		expected_payment_date: DF.Date | None
		financial_status: DF.Literal["", "Paid", "Partially Paid", "Partially Refunded", "Refunded", "Pending"]
		from_date: DF.Date | None
		fulfillment_completion_date: DF.Datetime | None
		fulfillment_status: DF.Literal["", "Fulfilled", "Not Fulfilled"]
		gender: DF.Data | None
		grand_total: DF.Currency
		group_payment_entries: DF.Table[PaymentEntryReference]
		group_same_items: DF.Check
		has_unit_price_items: DF.Check
		ignore_default_payment_terms_template: DF.Check
		haravan_coupon_code: DF.SmallText | None
		haravan_created_at: DF.Datetime | None
		haravan_order_id: DF.Data | None
		haravan_ref_order_id: DF.Data | None
		ignore_pricing_rule: DF.Check
		in_words: DF.Data | None
		incoterm: DF.Link | None
		inter_company_order_reference: DF.Link | None
		is_internal_customer: DF.Check
		is_subcontracted: DF.Check
		item_wise_tax_details: DF.Table[ItemWiseTaxDetail]
		is_split_order: DF.Check
		items: DF.Table[SalesOrderItem]
		language: DF.Link | None
		letter_head: DF.Link | None
		loyalty_amount: DF.Currency
		loyalty_points: DF.Int
		named_place: DF.Data | None
		naming_series: DF.Literal["SAL-ORD-.YYYY.-"]
		net_total: DF.Currency
		order_currency: DF.Link | None
		order_number: DF.Data | None
		order_policies: DF.LongText | None
		order_type: DF.Literal["Sales", "Maintenance", "Shopping Cart"]
		other_charges_calculation: DF.TextEditor | None
		packed_items: DF.Table[PackedItem]
		paid_amount: DF.Currency
		party_account_currency: DF.Link | None
		payment_completion_date: DF.Datetime | None
		payment_entries: DF.Table[PaymentEntryReference]
		payment_records: DF.Table[SalesOrderPaymentRecord]
		payment_schedule: DF.Table[PaymentSchedule]
		payment_terms_template: DF.Link | None
		per_billed: DF.Percent
		per_delivered: DF.Percent
		per_picked: DF.Percent
		place_of_issuance: DF.Data | None
		plc_conversion_rate: DF.Float
		po_date: DF.Date | None
		po_no: DF.Data | None
		policies: DF.TableMultiSelect[SalesOrderPolicy]
		price_list_currency: DF.Link
		pricing_rules: DF.Table[PricingRuleDetail]
		primary_sales_person: DF.Link | None
		product_categories: DF.TableMultiSelect[SalesOrderProductCategory]
		project: DF.Link | None
		promotions: DF.TableMultiSelect[SalesOrderPromotion]
		real_order_date: DF.Date | None
		ref_sales_orders: DF.Table[SalesOrderReference]
		represents_company: DF.Link | None
		reserve_stock: DF.Check
		return_amount: DF.Currency
		rounded_total: DF.Currency
		rounding_adjustment: DF.Currency
		sales_order_purposes: DF.TableMultiSelect[SalesOrderPurpose]
		sales_partner: DF.Link | None
		sales_team: DF.Table[SalesTeam]
		scan_barcode: DF.Data | None
		select_print_heading: DF.Link | None
		selling_price_list: DF.Link
		set_warehouse: DF.Link | None
		shipping_address: DF.TextEditor | None
		shipping_address_name: DF.Link | None
		shipping_rule: DF.Link | None
		skip_delivery_note: DF.Check
		source: DF.Link | None
		source_name: DF.Data | None
		split_order_group: DF.Data | None
		split_order_group_name: DF.Data | None
		split_reason: DF.Literal["", "Gold Regulation", "Customer Request", "Other"]
		status: DF.Literal["", "Draft", "On Hold", "To Deliver and Bill", "To Bill", "To Deliver", "Completed", "Cancelled", "Closed"]
		tax_category: DF.Link | None
		tax_id: DF.Data | None
		taxes: DF.Table[SalesTaxesandCharges]
		taxes_and_charges: DF.Link | None
		tc_name: DF.Link | None
		terms: DF.TextEditor | None
		territory: DF.Link | None
		to_date: DF.Date | None
		total: DF.Currency
		total_allocated_group_payment: DF.Currency
		total_amount: DF.Currency
		total_commission: DF.Currency
		total_net_weight: DF.Float
		total_qty: DF.Float
		total_taxes_and_charges: DF.Currency
		tracking_number: DF.Data | None
		transaction_date: DF.Date
		transaction_time: DF.Time | None
		utm_campaign: DF.Link | None
		utm_content: DF.Data | None
		utm_medium: DF.Link | None
		utm_source: DF.Link | None
	# end: auto-generated types

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.status_updater = [
			{
				"source_dt": "Sales Order Item",
				"target_dt": "Quotation Item",
				"join_field": "quotation_item",
				"target_field": "ordered_qty",
				"target_ref_field": "stock_qty",
				"source_field": "stock_qty",
			}
		]

	def onload(self) -> None:
		super().onload()
		self.set_payment_entries()
		self.set_group_payment_entries()


		if self.get("is_subcontracted"):
			self.set_onload("can_update_items", self.can_update_items())
			return

		if frappe.get_single_value("Stock Settings", "enable_stock_reservation"):
			if self.has_unreserved_stock():
				self.set_onload("has_unreserved_stock", True)

		if has_reserved_stock(self.doctype, self.name):
			self.set_onload("has_reserved_stock", True)

	def can_update_items(self) -> bool:
		result = True

		if self.is_subcontracted:
			if frappe.db.exists("Subcontracting Inward Order", {"sales_order": self.name, "docstatus": 1}):
				result = False

		return result

	def before_validate(self):
		self.set_has_unit_price_items()
		self.flags.allow_zero_qty = self.has_unit_price_items

	def set_payment_entries(self):
		"""Fetch and set the payment entries linked to this sales order."""
		if self.docstatus == 2 or not self.name:
			return

		self.set("payment_entries", [])

		# Get payment entries linked to this sales order
		payment_references = frappe.db.sql("""
			SELECT
				pr.name, pr.parenttype, pr.parent, pr.reference_doctype, pr.reference_name,
				pr.total_amount, pr.outstanding_amount, pr.unallocated_amount, pr.order_number, pr.split_order_group_name,
				pr.bank_account, pr.bank, pr.bank_account_no, pr.bank_account_branch, pr.ref_order_number, pr.ref_order_date,
				CASE
					WHEN pe.payment_type = 'Pay' THEN -pr.allocated_amount
					ELSE pr.allocated_amount
				END AS allocated_amount,
				pe.mode_of_payment, pe.gateway, pe.paid_amount, pe.payment_date, pe.payment_order_status, pe.payment_type
			FROM `tabPayment Entry Reference` pr
			INNER JOIN `tabPayment Entry` pe ON pr.parent = pe.name
			WHERE pr.reference_doctype = 'Sales Order' AND pr.reference_name = %s
			AND pe.docstatus < 2
			AND pe.payment_order_status = 'Success'
		""", self.name, as_dict=True)

		if not payment_references:
			return

		total_allocated = 0.0
		for pe_ref in payment_references:
			total_allocated += flt(pe_ref.allocated_amount)
			row = self.append("payment_entries", {})
			row.update({
					"name": pe_ref.name,
					"owner": "Administrator",
					"modified_by": "Administrator",
					"docstatus": 0,
					"reference_doctype": pe_ref.parenttype,
					"reference_name": pe_ref.parent,
					"total_amount": pe_ref.total_amount,
					"outstanding_amount": pe_ref.outstanding_amount,
					"unallocated_amount": pe_ref.unallocated_amount,
					"allocated_amount": pe_ref.allocated_amount,
					"parent": pe_ref.reference_name,
					"parentfield": "payment_entries",
					"parenttype": pe_ref.reference_doctype,
					"doctype": "Payment Entry Reference",
					"mode_of_payment": pe_ref.mode_of_payment,
					"gateway": pe_ref.gateway,
					"paid_amount": pe_ref.paid_amount,
					"payment_date": pe_ref.payment_date,
					"payment_order_status": pe_ref.payment_order_status,
					"order_number": pe_ref.order_number,
					"split_order_group_name": pe_ref.split_order_group_name,
					"bank_account": pe_ref.bank_account,
					"bank": pe_ref.bank,
					"bank_account_no": pe_ref.bank_account_no,
					"bank_account_branch": pe_ref.bank_account_branch,
					"ref_order_number": pe_ref.ref_order_number,
					"ref_order_date": pe_ref.ref_order_date,
			})


	def set_group_payment_entries(self):
		"""Fetch and set the payment entries linked to the split order group and reference tree."""
		if self.docstatus == 2:
			return

		related_orders = self.get_all_related_sales_orders()

		# If no related orders (including self), explicitly empty list
		if not related_orders:
			self.set("group_payment_entries", [])
			return

		self.set("group_payment_entries", [])

		payment_references = frappe.db.sql("""
			SELECT
				pr.name, pr.parenttype, pr.parent, pr.reference_doctype, pr.reference_name,
				pr.total_amount, pr.outstanding_amount, pr.unallocated_amount, pr.order_number, pr.split_order_group_name,
				pr.bank_account, pr.bank, pr.bank_account_no, pr.bank_account_branch, pr.ref_order_number, pr.ref_order_date,
				CASE
					WHEN pe.payment_type = 'Pay' THEN -pr.allocated_amount
					ELSE pr.allocated_amount
				END AS allocated_amount,
				pe.mode_of_payment, pe.gateway, pe.paid_amount, pe.payment_date, pe.payment_order_status, pe.payment_type
			FROM `tabPayment Entry Reference` pr
			INNER JOIN `tabPayment Entry` pe ON pr.parent = pe.name
			INNER JOIN `tabSales Order` so ON pr.reference_name = so.name
			WHERE pr.reference_doctype = 'Sales Order'
			AND so.name IN %s
			AND pe.docstatus < 2
			AND pe.payment_order_status = 'Success'
			ORDER BY pe.payment_date DESC
		""", (tuple(related_orders),), as_dict=True)

		if payment_references:
			for pe_ref in payment_references:
				row = self.append("group_payment_entries", {})
				row.update({
						"name": pe_ref.name,
						"owner": "Administrator",
						"modified_by": "Administrator",
						"docstatus": 0,
						"reference_doctype": pe_ref.parenttype,
						"reference_name": pe_ref.parent,
						"total_amount": pe_ref.total_amount,
						"outstanding_amount": pe_ref.outstanding_amount,
						"unallocated_amount": pe_ref.unallocated_amount,
						"allocated_amount": pe_ref.allocated_amount,
						"parent": pe_ref.reference_name,
						"parentfield": "group_payment_entries",
						"parenttype": pe_ref.reference_doctype,
						"doctype": "Payment Entry Reference",
						"mode_of_payment": pe_ref.mode_of_payment,
						"gateway": pe_ref.gateway,
						"paid_amount": pe_ref.paid_amount,
						"payment_date": pe_ref.payment_date,
						"payment_order_status": pe_ref.payment_order_status,
						"order_number": pe_ref.order_number,
						"split_order_group_name": pe_ref.split_order_group_name,
						"bank_account": pe_ref.bank_account,
						"bank": pe_ref.bank,
						"bank_account_no": pe_ref.bank_account_no,
						"bank_account_branch": pe_ref.bank_account_branch,
						"ref_order_number": pe_ref.ref_order_number,
						"ref_order_date": pe_ref.ref_order_date,
				})

	def get_all_related_sales_orders(self):
		"""
		Returns a set of Sales Order names that are related to this order via:
		1. Split Order Group (all orders with same split_order_group)
		2. Reference Tree (recursive traversal of ref_sales_orders)
		"""
		related_orders = set()
		if self.name:
			related_orders.add(self.name)

		# 1. Fetch by Split Order Group
		if self.is_split_order and self.split_order_group:
			group_orders = frappe.db.get_all("Sales Order",
				filters={
					"split_order_group": self.split_order_group,
					"is_split_order": 1
				},
				fields=["name"]
			)
			for o in group_orders:
				related_orders.add(o.name)

		# 2. Fetch by Reference Tree (Recursive)
		# We need to traverse:
		# - Down: Orders referenced by this order (ref_sales_orders child table)
		# - Up: Orders that reference this order (Ref Sales Order table of other orders)

		to_visit = list(related_orders)
		visited = set(related_orders)

		while to_visit:
			current_so = to_visit.pop()
			if not current_so:
				continue

			# A. Find orders referenced BY current_so
			refs_down = frappe.db.get_all("Sales Order Reference",
				filters={"parent": current_so},
				fields=["sales_order"]
			)

			for ref in refs_down:
				if ref.sales_order and ref.sales_order not in visited:
					visited.add(ref.sales_order)
					to_visit.append(ref.sales_order)
					related_orders.add(ref.sales_order)

			# B. Find orders referencing current_so
			refs_up = frappe.db.get_all("Sales Order Reference",
				filters={"sales_order": current_so},
				fields=["parent"]
			)

			for ref in refs_up:
				if ref.parent and ref.parent not in visited:
					visited.add(ref.parent)
					to_visit.append(ref.parent)
					related_orders.add(ref.parent)


		return list(related_orders)


	def validate(self):
		super().validate()
		self.validate_delivery_date()
		self.validate_proj_cust()
		self.validate_po()
		self.validate_uom_is_integer("stock_uom", "stock_qty")
		self.validate_uom_is_integer("uom", "qty")
		self.validate_for_items()
		self.validate_warehouse()
		self.validate_drop_ship()
		self.validate_reserved_stock()
		self.validate_serial_no_based_delivery()
		validate_against_blanket_order(self)
		validate_inter_company_party(
			self.doctype, self.customer, self.company, self.inter_company_order_reference
		)

		if self.coupon_code:
			from erpnext.accounts.doctype.pricing_rule.utils import validate_coupon_code

			validate_coupon_code(self.coupon_code)

		self.set_order_policies_summary()

		from erpnext.stock.doctype.packed_item.packed_item import make_packing_list

		make_packing_list(self)

		self.validate_with_previous_doc()
		self.validate_fg_item_for_subcontracting()
		self.set_status()

		if not self.billing_status:
			self.billing_status = "Not Billed"
		if not self.delivery_status:
			self.delivery_status = "Not Delivered"
		if not self.advance_payment_status:
			self.advance_payment_status = "Not Requested"

		self.reset_default_field_value("set_warehouse", "items", "warehouse")
		if not self.get("is_subcontracted"):
			self.enable_auto_reserve_stock()

	def validate_fg_item_for_subcontracting(self):
		if self.is_subcontracted:
			for item in self.items:
				if not item.fg_item:
					frappe.throw(
						_("Row #{0}: Finished Good Item is not specified for service item {1}").format(
							item.idx, item.item_code
						)
					)
				else:
					if not frappe.get_value("Item", item.fg_item, "is_sub_contracted_item"):
						frappe.throw(
							_("Row #{0}: Finished Good Item {1} must be a sub-contracted item").format(
								item.idx, item.fg_item
							)
						)
					if not frappe.db.get_value(
						"Subcontracting BOM",
						{"finished_good": item.fg_item, "is_active": 1},
						"finished_good_bom",
					) and not frappe.get_value("Item", item.fg_item, "default_bom"):
						frappe.throw(
							_("Row #{0}: BOM not found for FG Item {1}").format(item.idx, item.fg_item)
						)
				if not item.fg_item_qty:
					frappe.throw(_("Row #{0}: Finished Good Item Qty can not be zero").format(item.idx))
		else:
			for item in self.items:
				item.set("fg_item", None)
				item.set("fg_item_qty", 0)

	def enable_auto_reserve_stock(self):
		if self.is_new() and frappe.get_single_value("Stock Settings", "auto_reserve_stock"):
			self.reserve_stock = 1

	def set_has_unit_price_items(self):
		"""
		If permitted in settings and any item has 0 qty, the SO has unit price items.
		"""
		if not frappe.get_single_value("Selling Settings", "allow_zero_qty_in_sales_order"):
			return

		self.has_unit_price_items = any(
			not row.qty for row in self.get("items") if (row.item_code and not row.qty)
		)

	def validate_po(self):
		# validate p.o date v/s delivery date
		if self.po_date and not self.skip_delivery_note:
			for d in self.get("items"):
				if d.delivery_date and getdate(self.po_date) > getdate(d.delivery_date):
					frappe.throw(
						_("Row #{0}: Expected Delivery Date cannot be before Purchase Order Date").format(
							d.idx
						)
					)

		if self.po_no and self.customer and not self.skip_delivery_note:
			so = frappe.db.sql(
				"select name from `tabSales Order` \
				where ifnull(po_no, '') = %s and name != %s and docstatus < 2\
				and customer = %s",
				(self.po_no, self.name, self.customer),
			)
			if so and so[0][0]:
				if cint(
					frappe.get_single_value("Selling Settings", "allow_against_multiple_purchase_orders")
				):
					frappe.msgprint(
						_(
							"Warning: Sales Order {0} already exists against Customer's Purchase Order {1}"
						).format(frappe.bold(so[0][0]), frappe.bold(self.po_no)),
						alert=True,
					)
				else:
					frappe.throw(
						_(
							"Sales Order {0} already exists against Customer's Purchase Order {1}. To allow multiple Sales Orders, Enable {2} in {3}"
						).format(
							frappe.bold(so[0][0]),
							frappe.bold(self.po_no),
							frappe.bold(
								_("'Allow Multiple Sales Orders Against a Customer's Purchase Order'")
							),
							get_link_to_form("Selling Settings", "Selling Settings"),
						)
					)

	def validate_for_items(self):
		for d in self.get("items"):
			# used for production plan
			d.transaction_date = self.transaction_date

			tot_avail_qty = frappe.db.sql(
				"select projected_qty from `tabBin` \
				where item_code = %s and warehouse = %s",
				(d.item_code, d.warehouse),
			)
			d.projected_qty = (tot_avail_qty and flt(tot_avail_qty[0][0])) or 0

	def product_bundle_has_stock_item(self, product_bundle):
		"""Returns true if product bundle has stock item"""
		ret = len(
			frappe.db.sql(
				"""select i.name from tabItem i, `tabProduct Bundle Item` pbi
			where pbi.parent = %s and pbi.item_code = i.name and i.is_stock_item = 1""",
				product_bundle,
			)
		)
		return ret

	def validate_sales_mntc_quotation(self):
		for d in self.get("items"):
			if d.prevdoc_docname:
				res = frappe.db.sql(
					"select name from `tabQuotation` where name=%s and order_type = %s",
					(d.prevdoc_docname, self.order_type),
				)
				if not res:
					frappe.msgprint(
						_("Quotation {0} not of type {1}").format(d.prevdoc_docname, self.order_type)
					)

	def validate_delivery_date(self):
		if self.order_type == "Sales" and not self.skip_delivery_note:
			delivery_date_list = [d.delivery_date for d in self.get("items") if d.delivery_date]
			max_delivery_date = max(delivery_date_list) if delivery_date_list else None
			if (max_delivery_date and not self.delivery_date) or (
				max_delivery_date and getdate(self.delivery_date) != getdate(max_delivery_date)
			):
				self.delivery_date = max_delivery_date
			if self.delivery_date:
				for d in self.get("items"):
					if not d.delivery_date:
						d.delivery_date = self.delivery_date
					if getdate(self.transaction_date) > getdate(d.delivery_date):
						frappe.msgprint(
							_("Expected Delivery Date should be after Sales Order Date"),
							indicator="orange",
							title=_("Invalid Delivery Date"),
							raise_exception=True,
						)
			else:
				frappe.throw(_("Please enter Delivery Date"))

		self.validate_sales_mntc_quotation()

	def validate_proj_cust(self):
		if self.project and self.customer_name:
			res = frappe.db.sql(
				"""select name from `tabProject` where name = %s
				and (customer = %s or ifnull(customer,'')='')""",
				(self.project, self.customer),
			)
			if not res:
				frappe.throw(
					_("Customer {0} does not belong to project {1}").format(self.customer, self.project)
				)

	def validate_warehouse(self):
		super().validate_warehouse()

		for d in self.get("items"):
			if (
				(
					frappe.get_cached_value("Item", d.item_code, "is_stock_item") == 1
					or (
						self.has_product_bundle(d.item_code)
						and self.product_bundle_has_stock_item(d.item_code)
					)
				)
				and not d.warehouse
				and not cint(d.delivered_by_supplier)
			):
				frappe.throw(
					_("Delivery warehouse required for stock item {0}").format(d.item_code), WarehouseRequired
				)

	def validate_with_previous_doc(self):
		super().validate_with_previous_doc(
			{
				"Quotation": {"ref_dn_field": "prevdoc_docname", "compare_fields": [["company", "="]]},
				"Quotation Item": {
					"ref_dn_field": "quotation_item",
					"compare_fields": [["item_code", "="], ["uom", "="], ["conversion_factor", "="]],
					"is_child_table": True,
					"allow_duplicate_prev_row_id": True,
				},
			}
		)

		if cint(frappe.get_single_value("Selling Settings", "maintain_same_sales_rate")):
			self.validate_rate_with_reference_doc([["Quotation", "prevdoc_docname", "quotation_item"]])

	def update_enquiry_status(self, prevdoc, flag):
		enq = frappe.db.sql(
			"select t2.prevdoc_docname from `tabQuotation` t1, `tabQuotation Item` t2 where t2.parent = t1.name and t1.name=%s",
			prevdoc,
		)
		if enq:
			frappe.db.sql("update `tabOpportunity` set status = %s where name=%s", (flag, enq[0][0]))

	def update_prevdoc_status(self, flag=None):
		for quotation in set(d.prevdoc_docname for d in self.get("items")):
			if quotation:
				doc = frappe.get_doc("Quotation", quotation)
				if doc.docstatus.is_cancelled():
					frappe.throw(_("Quotation {0} is cancelled").format(quotation))

				doc.set_status(update=True)
				doc.update_opportunity("Converted" if flag == "submit" else "Quotation")

	def validate_drop_ship(self):
		for d in self.get("items"):
			if d.delivered_by_supplier and not d.supplier:
				frappe.throw(_("Row #{0}: Set Supplier for item {1}").format(d.idx, d.item_code))

	def on_submit(self):
		super().update_prevdoc_status()
		self.check_credit_limit()
		self.update_reserved_qty()
		self.delete_removed_delivery_schedule_items()

		frappe.get_cached_doc("Authorization Control").validate_approving_authority(
			self.doctype, self.company, self.base_grand_total, self
		)
		self.update_project()
		self.update_prevdoc_status("submit")

		self.update_blanket_order()

		update_linked_doc(self.doctype, self.name, self.inter_company_order_reference)
		if self.coupon_code:
			from erpnext.accounts.doctype.pricing_rule.utils import update_coupon_code_count

			update_coupon_code_count(self.coupon_code, "used")

		if self.get("reserve_stock") and not self.get("is_subcontracted"):
			self.create_stock_reservation_entries()

	def delete_removed_delivery_schedule_items(self):
		items = [d.name for d in self.get("items")]
		doctype = frappe.qb.DocType("Delivery Schedule Item")
		frappe.qb.from_(doctype).delete().where(
			(doctype.sales_order == self.name) & (doctype.sales_order_item.notin(items))
		).run()

	def on_cancel(self):
		self.ignore_linked_doctypes = (
			"GL Entry",
			"Stock Ledger Entry",
			"Payment Ledger Entry",
			"Advance Payment Ledger Entry",
			"Unreconcile Payment",
			"Unreconcile Payment Entries",
		)
		super().on_cancel()
		super().update_prevdoc_status()
		# Cannot cancel closed SO
		if self.status == "Closed":
			frappe.throw(_("Closed order cannot be cancelled. Unclose to cancel."))

		self.delete_delivery_schedule_items()
		self.check_nextdoc_docstatus()
		self.update_reserved_qty()
		self.update_project()
		self.update_prevdoc_status("cancel")

		self.db_set("status", "Cancelled")

		self.update_blanket_order()
		self.cancel_stock_reservation_entries()

		unlink_inter_company_doc(self.doctype, self.name, self.inter_company_order_reference)
		if self.coupon_code:
			from erpnext.accounts.doctype.pricing_rule.utils import update_coupon_code_count

			update_coupon_code_count(self.coupon_code, "cancelled")

	def update_project(self):
		if frappe.get_single_value("Selling Settings", "sales_update_frequency") != "Each Transaction":
			return

		if self.project:
			project = frappe.get_lazy_doc("Project", self.project)
			project.update_sales_amount()
			project.db_update()

	def check_credit_limit(self):
		# if bypass credit limit check is set to true (1) at sales order level,
		# then we need not to check credit limit and vise versa
		if not cint(
			frappe.db.get_value(
				"Customer Credit Limit",
				{"parent": self.customer, "parenttype": "Customer", "company": self.company},
				"bypass_credit_limit_check",
			)
		):
			check_credit_limit(self.customer, self.company)

	def check_nextdoc_docstatus(self):
		linked_invoices = frappe.db.sql_list(
			"""select distinct t1.name
			from `tabSales Invoice` t1,`tabSales Invoice Item` t2
			where t1.name = t2.parent and t2.sales_order = %s and t1.docstatus = 0""",
			self.name,
		)

		if linked_invoices:
			linked_invoices = [get_link_to_form("Sales Invoice", si) for si in linked_invoices]
			frappe.throw(
				_("Sales Invoice {0} must be deleted before cancelling this Sales Order").format(
					", ".join(linked_invoices)
				)
			)

	def check_modified_date(self):
		mod_db = frappe.db.get_value("Sales Order", self.name, "modified")
		date_diff = frappe.db.sql(f"select TIMEDIFF('{mod_db}', '{cstr(self.modified)}')")
		if date_diff and date_diff[0][0]:
			frappe.throw(_("{0} {1} has been modified. Please refresh.").format(self.doctype, self.name))

	def update_status(self, status):
		self.check_modified_date()
		self.set_status(update=True, status=status)
		# Upon Sales Order Re-open, check for credit limit.
		# Limit should be checked after the 'Hold/Closed' status is reset.
		if status == "Draft" and self.docstatus == 1:
			self.check_credit_limit()
		self.update_reserved_qty()
		self.update_subcontracting_order_status()
		self.notify_update()
		clear_doctype_notifications(self)

	def update_subcontracting_order_status(self):
		from erpnext.subcontracting.doctype.subcontracting_inward_order.subcontracting_inward_order import (
			update_subcontracting_inward_order_status as update_scio_status,
		)

		if self.is_subcontracted:
			scio = frappe.get_cached_value(
				"Subcontracting Inward Order", {"sales_order": self.name, "docstatus": 1}, "name"
			)

			if scio:
				update_scio_status(scio, "Closed" if self.status == "Closed" else None)

	def update_reserved_qty(self, so_item_rows=None):
		"""update requested qty (before ordered_qty is updated)"""
		item_wh_list = []

		def _valid_for_reserve(item_code, warehouse):
			if (
				item_code
				and warehouse
				and [item_code, warehouse] not in item_wh_list
				and frappe.get_cached_value("Item", item_code, "is_stock_item")
			):
				item_wh_list.append([item_code, warehouse])

		for d in self.get("items"):
			if (not so_item_rows or d.name in so_item_rows) and not d.delivered_by_supplier:
				if self.has_product_bundle(d.item_code):
					for p in self.get("packed_items"):
						if p.parent_detail_docname == d.name and p.parent_item == d.item_code:
							_valid_for_reserve(p.item_code, p.warehouse)
				else:
					_valid_for_reserve(d.item_code, d.warehouse)

		for item_code, warehouse in item_wh_list:
			update_bin_qty(item_code, warehouse, {"reserved_qty": get_reserved_qty(item_code, warehouse)})

	def on_update(self):
		self.check_status_changes_for_rank()
		self.sync_tracking_number_to_payment_entry()
		self.copy_from_reference_order()

	def sync_tracking_number_to_payment_entry(self):
		if not self.tracking_number:
			return

		if not self.has_value_changed("tracking_number"):
			return

		payment_entries = frappe.db.sql("""
			SELECT parent
			FROM `tabPayment Entry Reference`
			WHERE reference_doctype = 'Sales Order'
			AND reference_name = %s
			AND parenttype = 'Payment Entry'
			AND parentfield = 'references'
		""", (self.name,), as_dict=True)

		if not payment_entries:
			return

		for pe in payment_entries:
			pe_docstatus = frappe.db.get_value("Payment Entry", pe.parent, "docstatus")
			if pe_docstatus == 0:
				frappe.db.set_value("Payment Entry", pe.parent, "shipping_code", self.tracking_number)

	def validate_sensitive_coupons(self):
		"""
		US2: Check if haravan coupon codes are partner coupons and require customer identity image.
		Partner coupons are identified by having a hyphen "-" in the code.
		Supports multiple coupon codes separated by newline.
		"""
		if not self.haravan_coupon_code:
			return

		# Parse multiple coupon codes (separated by newline)
		coupon_codes = []
		for code in self.haravan_coupon_code.split("\n"):
			code = code.strip()
			if code:
				coupon_codes.append(code)

		# Check if any coupon code is a partner coupon
		partner_coupons = []
		for coupon_code in coupon_codes:
			if " " in coupon_code:
				continue

			parts = coupon_code.split("-")
			if len(parts) != 2:
				continue

			if parts[0] == "AP0001":
				continue

			if len(parts[1]) == 6:
				partner_coupons.append(coupon_code)

		if partner_coupons:
			# Check if customer has identity image
			has_image = frappe.db.get_value("Customer", self.customer, "customer_identity_image")
			if not has_image:
				frappe.throw(
					_("Đơn hàng sử dụng mã giới thiệu Partner {0} yêu cầu nhân viên phải upload hình ảnh xác minh vào hồ sơ khách hàng {1} trước khi cho phép lưu đơn hàng.").format(
						frappe.bold(", ".join(partner_coupons)),
						frappe.bold(self.customer)
					),
					title=_("Thiếu thông tin khách hàng")
				)

	def set_order_policies_summary(self):
		summary = []
		for d in self.items:
			if d.item_policy:
				summary.append(f"{d.item_name}:\n{d.item_policy}")

		if summary:
			self.order_policies = "\n\n".join(summary)
		else:
			self.order_policies = ""

	def on_update_after_submit(self):
		self.calculate_commission()
		self.calculate_contribution()
		self.check_credit_limit()

	def before_update_after_submit(self):
		self.validate_po()
		self.validate_drop_ship()
		self.validate_supplier_after_submit()
		self.validate_delivery_date()

	def check_status_changes_for_rank(self):
		should_reevaluate = False
		if self.has_value_changed("financial_status") and self.financial_status in ["Paid", "Partially Paid"]:
			should_reevaluate = True

		if self.has_value_changed("cancelled_status") and self.cancelled_status in ["Cancelled", "Uncancelled"]:
			should_reevaluate = True

		if should_reevaluate:
			frappe.enqueue(
				"erpnext.selling.doctype.customer.customer.reevaluate_customer_rank",
				customer_name=self.customer,
				queue="default",
				timeout=10
			)

	def validate_supplier_after_submit(self):
		"""Check that supplier is the same after submit if PO is already made"""
		exc_list = []

		for item in self.items:
			if item.supplier:
				supplier = frappe.db.get_value("Sales Order Item", item.name, "supplier")
				if item.ordered_qty > 0.0 and item.supplier != supplier:
					exc_list.append(
						_("Row #{0}: Not allowed to change Supplier as Purchase Order already exists").format(
							item.idx
						)
					)

		if exc_list:
			frappe.throw("\n".join(exc_list))

	def update_delivery_status(self):
		"""Update delivery status from Purchase Order for drop shipping"""
		tot_qty, delivered_qty = 0.0, 0.0

		for item in self.items:
			if item.delivered_by_supplier:
				item_delivered_qty = frappe.db.sql(
					"""select sum(qty)
					from `tabPurchase Order Item` poi, `tabPurchase Order` po
					where poi.sales_order_item = %s
						and poi.item_code = %s
						and poi.parent = po.name
						and po.docstatus = 1
						and po.status = 'Delivered'""",
					(item.name, item.item_code),
				)

				item_delivered_qty = item_delivered_qty[0][0] if item_delivered_qty else 0
				item.db_set("delivered_qty", flt(item_delivered_qty), update_modified=False)

			delivered_qty += min(item.delivered_qty, item.qty)
			tot_qty += item.qty

		if tot_qty != 0:
			self.db_set("per_delivered", flt(delivered_qty / tot_qty) * 100, update_modified=False)

	def update_picking_status(self):
		total_picked_qty = 0.0
		total_qty = 0.0
		per_picked = 0.0

		for so_item in self.items:
			if cint(
				frappe.get_cached_value("Item", so_item.item_code, "is_stock_item")
			) or self.has_product_bundle(so_item.item_code):
				total_picked_qty += flt(so_item.picked_qty)
				total_qty += flt(so_item.stock_qty)

		if total_picked_qty and total_qty:
			per_picked = total_picked_qty / total_qty * 100

			pick_percentage = frappe.get_single_value("Stock Settings", "over_picking_allowance")
			if pick_percentage:
				total_qty += flt(total_qty) * (pick_percentage / 100)

			if total_picked_qty > total_qty:
				frappe.throw(
					_(
						"Total Picked Quantity {0} is more than ordered qty {1}. You can set the Over Picking Allowance in Stock Settings."
					).format(total_picked_qty, total_qty)
				)

		self.db_set("per_picked", flt(per_picked), update_modified=False)

	def set_indicator(self):
		"""Set indicator for portal"""
		self.indicator_color = {
			"Draft": "red",
			"On Hold": "orange",
			"To Deliver and Bill": "orange",
			"To Bill": "orange",
			"To Deliver": "orange",
			"Completed": "green",
			"Cancelled": "red",
		}.get(self.status, "blue")

		self.indicator_title = _(self.status)

	def on_recurring(self, reference_doc, auto_repeat_doc):
		def _get_delivery_date(ref_doc_delivery_date, red_doc_transaction_date, transaction_date):
			delivery_date = auto_repeat_doc.get_next_schedule_date(schedule_date=ref_doc_delivery_date)

			if delivery_date <= transaction_date:
				delivery_date_diff = frappe.utils.date_diff(ref_doc_delivery_date, red_doc_transaction_date)
				delivery_date = frappe.utils.add_days(transaction_date, delivery_date_diff)

			return delivery_date

		self.set(
			"delivery_date",
			_get_delivery_date(
				reference_doc.delivery_date, reference_doc.transaction_date, self.transaction_date
			),
		)

		for d in self.get("items"):
			reference_delivery_date = frappe.db.get_value(
				"Sales Order Item",
				{"parent": reference_doc.name, "item_code": d.item_code, "idx": d.idx},
				"delivery_date",
			)

			d.set(
				"delivery_date",
				_get_delivery_date(
					reference_delivery_date, reference_doc.transaction_date, self.transaction_date
				),
			)

	def validate_serial_no_based_delivery(self):
		reserved_items = []
		normal_items = []
		for item in self.items:
			if item.ensure_delivery_based_on_produced_serial_no:
				if item.item_code in normal_items:
					frappe.throw(
						_(
							"Cannot ensure delivery by Serial No as Item {0} is added with and without Ensure Delivery by Serial No."
						).format(item.item_code)
					)
				if item.item_code not in reserved_items:
					if not frappe.get_cached_value("Item", item.item_code, "has_serial_no"):
						frappe.throw(
							_(
								"Item {0} has no Serial No. Only serialized items can have delivery based on Serial No"
							).format(item.item_code)
						)
					if not frappe.db.exists("BOM", {"item": item.item_code, "is_active": 1}):
						frappe.throw(
							_(
								"No active BOM found for item {0}. Delivery by Serial No cannot be ensured"
							).format(item.item_code)
						)
				reserved_items.append(item.item_code)
			else:
				normal_items.append(item.item_code)

			if not item.ensure_delivery_based_on_produced_serial_no and item.item_code in reserved_items:
				frappe.throw(
					_(
						"Cannot ensure delivery by Serial No as Item {0} is added with and without Ensure Delivery by Serial No."
					).format(item.item_code)
				)

	def validate_reserved_stock(self):
		"""Clean reserved stock flag for non-stock Item"""

		enable_stock_reservation = frappe.get_single_value("Stock Settings", "enable_stock_reservation")

		for item in self.items:
			if item.reserve_stock and (not enable_stock_reservation or not cint(item.is_stock_item)):
				item.reserve_stock = 0

	def has_unreserved_stock(self) -> bool:
		"""Returns True if there is any unreserved item in the Sales Order."""

		reserved_qty_details = get_sre_reserved_qty_details_for_voucher("Sales Order", self.name)

		for item in self.get("items"):
			if not item.get("reserve_stock"):
				continue

			unreserved_qty = get_unreserved_qty(item, reserved_qty_details)
			if unreserved_qty > 0:
				return True

		return False

	@frappe.whitelist()
	def create_stock_reservation_entries(
		self,
		items_details: list[dict] | None = None,
		from_voucher_type: Literal["Pick List", "Purchase Receipt"] = None,
		notify=True,
	) -> None:
		"""Creates Stock Reservation Entries for Sales Order Items."""

		from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import (
			create_stock_reservation_entries_for_so_items as create_stock_reservation_entries,
		)

		create_stock_reservation_entries(
			sales_order=self,
			items_details=items_details,
			from_voucher_type=from_voucher_type,
			notify=notify,
		)

	@frappe.whitelist()
	def cancel_stock_reservation_entries(self, sre_list=None, notify=True) -> None:
		"""Cancel Stock Reservation Entries for Sales Order Items."""

		from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import (
			cancel_stock_reservation_entries,
		)

		cancel_stock_reservation_entries(
			voucher_type=self.doctype, voucher_no=self.name, sre_list=sre_list, notify=notify
		)
	def set_missing_values(self, for_validate=False):
		super().set_missing_values(for_validate)

		if self.delivery_date:
			for item in self.items:
				if not item.delivery_date:
					item.delivery_date = self.delivery_date

	@frappe.whitelist()
	def get_delivery_schedule(self, sales_order_item):
		return frappe.get_all(
			"Delivery Schedule Item",
			filters={"sales_order_item": sales_order_item, "sales_order": self.name},
			fields=["delivery_date", "qty", "name"],
			order_by="delivery_date asc",
		)

	@frappe.whitelist()
	def create_delivery_schedule(self, child_row, schedules):
		if isinstance(child_row, dict):
			child_row = frappe._dict(child_row)

		if isinstance(schedules, str):
			schedules = parse_json(schedules)

		names = []
		first_delivery_date = None
		for row in schedules:
			row = frappe._dict(row)

			if not first_delivery_date:
				first_delivery_date = row.delivery_date

			data = {
				"delivery_date": row.delivery_date,
				"qty": row.qty,
				"uom": child_row.uom,
				"stock_uom": child_row.stock_uom,
				"item_code": child_row.item_code,
				"conversion_factor": child_row.conversion_factor or 1.0,
				"warehouse": child_row.warehouse,
				"sales_order_item": child_row.name,
				"sales_order": self.name,
				"stock_qty": row.qty * (child_row.conversion_factor or 1.0),
			}

			if frappe.db.exists("Delivery Schedule Item", row.name):
				doc = frappe.get_doc("Delivery Schedule Item", row.name)
			else:
				doc = frappe.new_doc("Delivery Schedule Item")

			doc.update(data)
			doc.save(ignore_permissions=True)
			names.append(doc.name)

		if names:
			self.delete_delivery_schedule_items(child_row.name, names)

		if first_delivery_date:
			self.update_delivery_date_based_on_schedule(child_row, first_delivery_date)

	def update_delivery_date_based_on_schedule(self, child_row, first_delivery_date):
		for row in self.items:
			if row.name == child_row.name:
				if first_delivery_date:
					row.delivery_date = first_delivery_date
				break

		self.save()

	def delete_delivery_schedule_items(self, sales_order_item=None, ignore_names=None):
		"""Delete delivery schedule items."""
		doctype = frappe.qb.DocType("Delivery Schedule Item")

		query = frappe.qb.from_(doctype).delete().where(doctype.sales_order == self.name)

		if ignore_names:
			query = query.where(doctype.name.notin(ignore_names))

		if sales_order_item:
			query = query.where(doctype.sales_order_item == sales_order_item)

		query.run()

	def handle_order_cancellation(self):
		"""If order from Haravan is cancelled, cancel the current order too"""

		if self.cancelled_status == "Cancelled":
			if self.docstatus == DocStatus.SUBMITTED:  # Only cancel submitted documents
				self.cancel()
				return
			if self.docstatus == DocStatus.DRAFT:  # For draft documents
				self.flags.ignore_permissions = True
				self.docstatus = DocStatus.CANCELLED
				self.flags.ignore_on_cancel = True

	def validate_primary_sales_team(self):
		if self.sales_team and self.primary_sales_person:
			if len([t for t in self.sales_team if t.sales_person == self.primary_sales_person]) == 0:
				frappe.throw(_("Primary Sales Person must be part of the Sales Team."))

	def before_save(self):
		self.validate_primary_sales_team()
		self.process_debt_history()
		self.handle_serial_numbers_changes()

	def before_insert(self):
		self.process_debt_history()

	def process_debt_history(self):
		for row in self.get("debt_history"):
			# Only process newly added child rows
			is_new_row = (getattr(row, "is_new", None) and row.is_new()) or row.get("__islocal") or not row.name
			if not is_new_row:
				continue
			if hasattr(row, "update_added_by"):
				row.update_added_by()
			if hasattr(row, "_notify_assigned_user"):
				row._notify_assigned_user()

	def after_insert(self):
		self.update_customer_revenue_fields()
		self.copy_from_reference_order()
		self.auto_detect_split_orders()
		self.update_ref_order_payment_entry_current_order_number()
		self.copy_ref_order_payment_entries_to_current()

	def before_submit(self):
		frappe.throw(_("Sales Order Submission is not allowed."))

	def update_customer_revenue_fields(self):
		cumulative = self.calculate_customer_cumulative_revenue()
		true_cumulative = self.calculate_customer_true_cumulative_revenue()

		frappe.db.set_value("Customer", self.customer, {
			"cumulative_revenue": cumulative,
			"true_cumulative_revenue": true_cumulative
		})

	def update_ref_order_payment_entry_current_order_number(self):
		"""
		Update current order number for Payment Entry Reference linked to the original reference order
		"""
		try:
			if not self.haravan_ref_order_id:
				return

			ref_order_name = frappe.db.get_value("Sales Order",
				{"haravan_order_id": self.haravan_ref_order_id}, "name")

			if not ref_order_name:
				return

			current_order_number = self.order_number
			current_transaction_date = self.transaction_date

			frappe.db.sql("""
				UPDATE `tabPayment Entry Reference`
				SET
					ref_order_number = %s,
					ref_order_date = %s
				WHERE
					parenttype = 'Sales Order'
					AND parentfield = 'payment_entries'
					AND parent = %s
			""", (current_order_number, current_transaction_date, ref_order_name))

		except Exception as e:
			frappe.log_error(f"Error updating payment entry reference order number: {e!s}")

	def copy_ref_order_payment_entries_to_current(self):
		try:
			if not self.haravan_ref_order_id:
				return

			ref_order_name = frappe.db.get_value("Sales Order",
				{"haravan_order_id": self.haravan_ref_order_id}, "name")

			if not ref_order_name:
				return

			ref_rows = frappe.db.get_all(
				"Payment Entry Reference",
				filters={
					"parenttype": "Sales Order",
					"parentfield": "payment_entries",
					"parent": ref_order_name
				},
				fields=["*"]
			)

			if not ref_rows:
				return

			def _build_row(parent_name):
				new_row = frappe.new_doc("Payment Entry Reference")
				for field, value in row_dict.items():
					if field not in ("name", "creation", "modified", "modified_by", "owner",
									"parent", "parentfield", "parenttype", "idx"):
						setattr(new_row, field, value)
				new_row.parent = parent_name
				new_row.parentfield = "sales_order_payment_entries"
				new_row.parenttype = "Sales Order"
				new_row.idx = idx
				return new_row

			for idx, row in enumerate(ref_rows, start=1):
				row_dict = dict(row)
				_build_row(self.name).insert(ignore_permissions=True)
				_build_row(ref_order_name).insert(ignore_permissions=True)

		except Exception as e:
			frappe.log_error(f"Error copying payment entry references to current order: {e!s}")

	def calculate_customer_cumulative_revenue(self):
		result = frappe.db.sql("""
			SELECT SUM(grand_total)
			FROM `tabSales Order`
			WHERE customer = %s AND cancelled_status = 'Uncancelled'
		""", (self.customer,), as_list=True)
		return result[0][0] if result and result[0][0] else 0

	def calculate_customer_true_cumulative_revenue(self):
		result = frappe.db.sql("""
			SELECT SUM(grand_total)
			FROM `tabSales Order`
			WHERE customer = %s
			AND cancelled_status = 'Uncancelled'
			AND financial_status = 'Paid'
			AND fulfillment_status = 'Fulfilled'
		""", (self.customer,), as_list=True)
		return result[0][0] if result and result[0][0] else 0

	def copy_from_reference_order(self):
		"""Copy manual fields from previous order when haravan_ref_order_id is set"""
		if not self.haravan_ref_order_id:
			return
		try:
			# Get the reference order
			ref_order_name = frappe.db.get_value("Sales Order",
				{"haravan_order_id": self.haravan_ref_order_id}, "name")
			if not ref_order_name:
				return
			# Define simple fields to copy (data types)
			simple_fields = [
				'consultation_date', 'primary_sales_person',
				'deposit_location', 'delivery_location', 'expected_delivery_date',
				'customer_type', 'expected_payment_date',
				'deposit_amount', 'deposit_method',
				'order_currency', 'billing_address',
				'deposit_in_words', 'is_split_order',
				'split_order_group', 'split_order_group_name',
				'split_reason',
			]

			# Copy simple fields
			ref_data = frappe.db.get_value("Sales Order", ref_order_name, simple_fields, as_dict=True)
			if ref_data:
				update_fields = {}
				for field in simple_fields:
					ref_value = getattr(ref_data, field, None)
					current_value = getattr(self, field, None)
					if ref_value and not current_value:
						update_fields[field] = ref_value

				if update_fields:
					for field, value in update_fields.items():
						frappe.db.set_value("Sales Order", self.name, field, value)
						setattr(self, field, value)

			# Copy Table MultiSelect fields
			ref_order_doc = frappe.get_doc("Sales Order", ref_order_name)
			multiselect_fields = {
				# parentfield: link_field
				"policies": "policy",
				"promotions": "promotion",
				"product_categories": "product_category",
				"sales_order_purposes": "purchase_purpose"
			}

			for parentfield, link_field in multiselect_fields.items():
				current_rows = self.get(parentfield) or []
				ref_rows = ref_order_doc.get(parentfield) or []

				if not current_rows and ref_rows:
					for ref_row in ref_rows:
						child = self.append(parentfield, {link_field: getattr(ref_row, link_field)})
						child.db_insert()

			# Copy Table fields
			table_fields = ["sales_team", "debt_history"]
			for parentfield in table_fields:
				current_rows = self.get(parentfield) or []
				ref_rows = ref_order_doc.get(parentfield) or []
				if not current_rows and ref_rows:
					for ref_row in ref_rows:
						row = copy.deepcopy(ref_row.as_dict())
						# remove system fields
						for k in ("name", "parent", "parenttype", "parentfield", "creation", "modified", "modified_by", "owner", "docstatus", "idx"):
							row.pop(k, None)
						child = self.append(parentfield, row)
						child.db_insert()

			# Copy Sales Order Items
			self.copy_sales_order_items_from_reference(ref_order_doc)

			# Copy Attachments
			self.copy_attachments_from_reference(ref_order_name)

			# Copy Buyback Items
			self.copy_buyback_items_from_reference(ref_order_name)

		except Exception as e:
			frappe.log_error(f"Error copying from reference order: {e!s}")

	def copy_buyback_items_from_reference(self, ref_order_name):
		"""Duplicate Buyback Exchange Items from reference order to current order"""
		try:
			already_copied = frappe.db.exists(
				"Buyback Exchange Item", {"current_sales_order": self.name}
			)
			if already_copied:
				return

			buyback_items = frappe.get_all(
				"Buyback Exchange Item",
				filters={"current_sales_order": ref_order_name},
				fields=["name"]
			)

			if not buyback_items:
				return

			for item in buyback_items:
				original_doc = frappe.get_doc("Buyback Exchange Item", item.name)
				new_doc = frappe.copy_doc(original_doc)

				new_doc.current_sales_order = self.name
				new_doc.prev_sales_order = original_doc.prev_sales_order
				new_doc.amended_from = None

				new_doc.insert(ignore_permissions=True)

			if original_doc and original_doc.parent:
				frappe.db.sql("""
					UPDATE `tabBuyback Exchange`
					SET modified = %s
					WHERE name = %s
				""", (frappe.utils.now(), original_doc.parent))

			_update_sales_order_return_amount(self.name)

		except Exception as e:
			frappe.log_error(f"Error copying buyback items from reference order: {e!s}")

	def copy_attachments_from_reference(self, ref_order_name):
		"""Copy attachments from reference order to current order"""
		try:
			# Get all attachments from reference order
			attachments = frappe.get_all(
				"File",
				filters={
					"attached_to_doctype": "Sales Order",
					"attached_to_name": ref_order_name
				},
				fields=["name"]
			)

			if not attachments:
				return

			# Update each attachment to point to the new order
			for attachment in attachments:
				frappe.db.set_value("File", attachment.name, {
					"attached_to_name": self.name
				})

			frappe.db.commit()

		except Exception as e:
			frappe.log_error(f"Error copying attachments from reference order: {e!s}")

	def handle_serial_numbers_changes(self):
		"""Handle serial_numbers changes and backfill from reference orders"""
		try:
			if not self.haravan_ref_order_id:
				return
			# Get current items with serial_numbers
			current_items = self.get("items") or []
			items_with_serial = [item for item in current_items if getattr(item, "serial_numbers", None)]

			if not items_with_serial:
				return

			# Get previous serial_number data
			previous_serial_data = self._get_previous_serial_numbers()

			# Process each item with serial_numbers that has changed
			for current_item in items_with_serial:
				# Check if serial_numbers changed
				current_serial = getattr(current_item, "serial_numbers", None)
				previous_serial = previous_serial_data.get(current_item.name)

				# Only process if serial_numbers changed
				if current_serial != previous_serial and current_serial:
					self._backfill_item_from_reference_by_serial(current_item)

		except Exception as e:
			frappe.log_error(f"Error handling serial_numbers changes: {e!s}")

	def _get_previous_serial_numbers(self):
		"""Get previous serial_numbers from database for comparison"""
		try:
			# Get current serial_numbers from database
			serial_data = frappe.db.sql("""
				SELECT name, serial_numbers
				FROM `tabSales Order Item`
				WHERE parent = %s
			""", (self.name,), as_dict=True)
			return {item.name: item.serial_numbers for item in serial_data}
		except Exception as e:
			frappe.log_error(f"Error getting previous serial_numbers: {e!s}")
			return {}

	def _backfill_item_from_reference_by_serial(self, current_item):
		"""Backfill current item from reference item with matching serial_numbers"""
		try:
			current_serial = getattr(current_item, "serial_numbers", None)
			if not current_serial:
				return

			ref_order_names = get_candidate_reference_orders(
				source_order=self.name,
				haravan_ref_order_id=self.haravan_ref_order_id,
				split_order_group=self.split_order_group,
				is_split_order=self.is_split_order
			)
			if not ref_order_names:
				return

			matching_ref_item = None
			for name in ref_order_names:
				ref_order_doc = frappe.get_doc("Sales Order", name)
				ref_items = ref_order_doc.get("items") or []
				matching_ref_item = self._find_matching_ref_item_by_serial(ref_items, current_serial)
				if matching_ref_item:
					break

			if not matching_ref_item:
				return

			# Copy fields from reference item to current item
			self._copy_item_fields(matching_ref_item, current_item)

		except Exception as e:
			frappe.log_error(f"Error backfilling item {current_item.name}: {e!s}")

	def _find_matching_ref_item_by_serial(self, ref_items, current_serial):
		"""Find reference item with matching serial_numbers"""
		current_tokens = _tokenize_serials(current_serial)

		for ref_item in ref_items:
			ref_serial = getattr(ref_item, "serial_numbers", None)
			if not ref_serial:
				continue
			if current_tokens & _tokenize_serials(ref_serial):
				return ref_item
		return None

	def _copy_item_fields(self, ref_item, current_item):
		"""Copy fields from reference item to current item"""
		fields_to_copy = self._get_item_fields_to_copy()

		for field in fields_to_copy:
			ref_value = getattr(ref_item, field, None)
			current_value = getattr(current_item, field, None)

			# Only copy if reference has value and current doesn't
			if ref_value and not current_value:
				setattr(current_item, field, ref_value)

	def _map_current_and_ref_items(self, current_items, ref_items):
		"""Return (current_item, ref_item) pairs."""
		def norm(v):
			return str(v).strip() if v is not None else None

		def get_gia_from_sku(item):
			sku = getattr(item, "sku", None)
			if not sku:
				return None
			sku = str(sku)
			pos = sku.find("GIA")
			if pos < 0:
				return None
			start = pos + 3
			end = start + 10
			return sku[start:end] if end <= len(sku) else None

		def is_jewelry(item):
			sku = str(getattr(item, "sku", "") or "")
			parts = sku.split("-")
			is_gift = sku.startswith("QT")
			is_diamond = any(p.startswith("GIA") for p in parts)
			return not (is_gift or is_diamond)

		def get_serial(item):
			s = getattr(item, "serial_numbers", "")
			return str(s).strip() if s else None

		ref_by_variant = {}
		ref_by_gia = {}
		ref_by_serial = {}
		for ref in ref_items:
			vid = norm(getattr(ref, "haravan_variant_id", None))
			if vid:
				ref_by_variant[vid] = ref
			gia = get_gia_from_sku(ref)
			if gia and gia not in ref_by_gia:
				ref_by_gia[gia] = ref
			serial = get_serial(ref)
			if serial and is_jewelry(ref):
				for token in _tokenize_serials(serial):
					if token not in ref_by_serial:
						ref_by_serial[token] = ref

		pairs = []
		matched = set()

		# Pass 1: Match by Haravan Variant ID
		for cur in current_items:
			vid = norm(getattr(cur, "haravan_variant_id", None))
			if vid and vid in ref_by_variant:
				pairs.append((cur, ref_by_variant[vid]))
				matched.add(cur.name)

		# Pass 2: Match by GIA (Diamond)
		for cur in current_items:
			if cur.name in matched:
				continue
			gia = get_gia_from_sku(cur)
			if gia and gia in ref_by_gia:
				pairs.append((cur, ref_by_gia[gia]))
				matched.add(cur.name)

		# Pass 3: Match by Serial Number (Jewelry only, non-gift, non-diamond)
		for cur in current_items:
			if cur.name in matched:
				continue
			if not is_jewelry(cur):
				continue
			serial = get_serial(cur)
			if not serial:
				continue
			for token in _tokenize_serials(serial):
				if token in ref_by_serial:
					pairs.append((cur, ref_by_serial[token]))
					matched.add(cur.name)
					break

		return pairs

	def _get_item_fields_to_copy(self):
		"""Central place to define manual fields to copy between items."""
		return [
			'product_details',
			'diamond_details',
			'product_availability_status',
			'serial_numbers',
			'new_promotions',
			'promotion_1',
			'promotion_2',
			'promotion_3',
			'promotion_4',
			'promotion_5',
			'uom',
			'weight_per_unit',
			'weight_uom',
			'image',
			'discount_rate',
			'item_policy',
			'is_policy_locked'
		]


	def copy_sales_order_items_from_reference(self, ref_order_doc):
		"""Copy Sales Order Items from reference order based on haravan_variant_id mapping"""
		try:
			current_items = self.get("items") or []
			ref_items = ref_order_doc.get("items") or []

			if not current_items or not ref_items:
				return

			# Build mapping pairs: current_item - ref_item
			pairs = self._map_current_and_ref_items(current_items, ref_items)
			if not pairs:
				return

			# Update current items with reference data using frappe.db.set_value for child table
			items_updated = False
			for current_item, ref_item in pairs:
				# Copy fields using common method
				items_updated = self._copy_item_fields_with_db_update(ref_item, current_item) or items_updated

			if items_updated:
				frappe.db.commit()
				frappe.clear_document_cache("Sales Order", self.name)

		except Exception as e:
			frappe.log_error(f"Error copying SO items: {str(e)[:100]}")

	def _copy_item_fields_with_db_update(self, ref_item, current_item):
		"""Copy fields from reference item to current item using frappe.db.set_value"""
		fields_to_copy = self._get_item_fields_to_copy()
		items_updated = False

		for field in fields_to_copy:
			ref_value = getattr(ref_item, field, None)
			current_value = getattr(current_item, field, None)

			# Special handling for uom field - always copy if reference has value
			if field == 'uom' and ref_value:
				frappe.db.set_value("Sales Order Item", current_item.name, field, ref_value)
				items_updated = True
			# For other fields, only copy if reference has value and current item doesn't have value
			elif ref_value and not current_value:
				frappe.db.set_value("Sales Order Item", current_item.name, field, ref_value)
				items_updated = True

		return items_updated

	def auto_detect_split_orders(self):
		"""
		Auto-detect split orders based on customer and order creation time
		"""

		# Skip if not is_split_order
		if self.is_split_order:
			return
		# Skip if no haravan_created_at (cannot detect time-based)
		if not self.haravan_created_at:
			return

		# Calculate time window (30 minutes BEFORE current order time only)
		order_time = get_datetime(self.haravan_created_at)
		time_window_start = add_to_date(order_time, minutes=-30)

		# Find orders from same customer created within 30 minutes before
		# Only look for new orders (not reorders) to avoid grouping unrelated orders
		previous_orders = frappe.db.sql("""
			SELECT
				name,
				haravan_order_id,
				haravan_created_at,
				split_order_group,
				split_order_group_name,
				is_split_order,
				order_number
			FROM `tabSales Order`
			WHERE customer = %s
				AND haravan_created_at >= %s
				AND haravan_created_at < %s
				AND name != %s
				AND cancelled_status = 'Uncancelled'
			LIMIT 10
		""", (self.customer, time_window_start, order_time, self.name), as_dict=True)

		if not previous_orders:
			frappe.db.sql("""
				UPDATE `tabSales Order`
				SET split_order_group = %s,
					split_order_group_name = %s,
					is_split_order = 0
				WHERE name = %s
				ORDER BY haravan_created_at ASC
			""", (self.haravan_order_id, self.order_number, self.name))

			# Sync with self object
			self.split_order_group = self.haravan_order_id
			self.split_order_group_name = self.order_number
			self.is_split_order = 0

			frappe.db.commit()
			return

		# Found related order(s) → This is a split order
		first_previous_order = previous_orders[0]

		# Get group ID from previous order
		split_group_id = first_previous_order.split_order_group or first_previous_order.haravan_order_id
		split_group_name = first_previous_order.split_order_group_name or first_previous_order.order_number

		# Set this order as split order
		frappe.db.sql("""
			UPDATE `tabSales Order`
			SET split_order_group = %s,
				split_order_group_name = %s,
				is_split_order = 1,
				split_reason = 'Gold Regulation'
			WHERE name = %s
		""", (split_group_id, split_group_name, self.name))

		# Sync with self object
		self.split_order_group = split_group_id
		self.split_order_group_name = split_group_name
		self.is_split_order = 1
		self.split_reason = 'Gold Regulation'

		# Update all previous orders to mark as split orders
		for prev_order in previous_orders:
			# Always update to ensure is_split_order = 1
			frappe.db.sql("""
				UPDATE `tabSales Order`
				SET split_order_group = %s,
					split_order_group_name = %s,
					is_split_order = 1,
					split_reason = 'Gold Regulation'
				WHERE name = %s
			""", (split_group_id, split_group_name, prev_order.name))

		frappe.db.commit()

def get_unreserved_qty(item: object, reserved_qty_details: dict) -> float:
	"""Returns the unreserved quantity for the Sales Order Item."""

	existing_reserved_qty = reserved_qty_details.get(item.name, 0)
	return item.stock_qty - flt(item.delivered_qty) * item.get("conversion_factor", 1) - existing_reserved_qty


def get_list_context(context=None):
	from erpnext.controllers.website_list_for_contact import get_list_context

	list_context = get_list_context(context)
	list_context.update(
		{
			"show_sidebar": True,
			"show_search": True,
			"no_breadcrumbs": True,
			"title": _("Orders"),
			"list_template": "templates/includes/list/list.html",
		}
	)

	return list_context


@frappe.whitelist()
def is_enable_cutoff_date_on_bulk_delivery_note_creation():
	return frappe.get_single_value("Selling Settings", "enable_cutoff_date_on_bulk_delivery_note_creation")


@frappe.whitelist()
def close_or_unclose_sales_orders(names, status):
	if not frappe.has_permission("Sales Order", "write"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	names = json.loads(names)
	for name in names:
		so = frappe.get_lazy_doc("Sales Order", name)
		if so.docstatus == 1:
			if status == "Closed":
				if so.status not in ("Cancelled", "Closed") and (
					so.per_delivered < 100 or so.per_billed < 100
				):
					so.update_status(status)
			else:
				if so.status == "Closed":
					so.update_status("Draft")
			so.update_blanket_order()

	frappe.local.message_log = []


def get_requested_item_qty(sales_order):
	result = {}

	so = frappe.get_doc("Sales Order", sales_order)

	for item in so.items:
		if is_product_bundle(item.item_code):
			for packed_item in so.get("packed_items"):
				if (
					packed_item.parent_item == item.item_code
					and packed_item.parent_detail_docname == item.name
				):
					result[packed_item.name] = frappe._dict({"qty": packed_item.requested_qty})
		else:
			result[item.name] = frappe._dict({"qty": item.requested_qty})

	return result


@frappe.whitelist()
def make_material_request(source_name, target_doc=None):
	requested_item_qty = get_requested_item_qty(source_name)

	def postprocess(source, target):
		if source.tc_name and frappe.db.get_value("Terms and Conditions", source.tc_name, "buying") != 1:
			target.tc_name = None
			target.terms = None

	def get_remaining_qty(so_item):
		return flt(
			flt(so_item.qty)
			- flt(requested_item_qty.get(so_item.name, {}).get("qty"))
			- max(
				flt(so_item.get("delivered_qty")),
				0,
			)
		)

	def get_remaining_packed_item_qty(so_item):
		delivered_qty = frappe.db.get_value(
			"Sales Order Item", {"name": so_item.parent_detail_docname}, ["delivered_qty"]
		)

		bundle_item_qty = frappe.db.get_value(
			"Product Bundle Item", {"parent": so_item.parent_item, "item_code": so_item.item_code}, ["qty"]
		)

		return flt(
			flt(so_item.qty)
			- flt(requested_item_qty.get(so_item.name, {}).get("qty"))
			- max(
				flt(delivered_qty) * flt(bundle_item_qty),
				0,
			)
		)

	def update_item(source, target, source_parent):
		# qty is for packed items, because packed items don't have stock_qty field
		target.project = source_parent.project
		target.qty = (
			get_remaining_packed_item_qty(source)
			if source.parentfield == "packed_items"
			else get_remaining_qty(source)
		)
		target.stock_qty = flt(target.qty) * flt(target.conversion_factor)
		target.actual_qty = get_bin_details(
			target.item_code, target.warehouse, source_parent.company, True
		).get("actual_qty", 0)

		ctx = ItemDetailsCtx(target.as_dict().copy())
		ctx.update(
			{
				"company": source_parent.get("company"),
				"price_list": frappe.db.get_single_value("Buying Settings", "buying_price_list"),
				"currency": source_parent.get("currency"),
				"conversion_rate": source_parent.get("conversion_rate"),
			}
		)

		target.rate = flt(
			get_price_list_rate(ctx, item_doc=frappe.get_cached_doc("Item", target.item_code)).get(
				"price_list_rate"
			)
		)
		target.amount = target.qty * target.rate

	doc = get_mapped_doc(
		"Sales Order",
		source_name,
		{
			"Sales Order": {"doctype": "Material Request", "validation": {"docstatus": ["=", 1]}},
			"Packed Item": {
				"doctype": "Material Request Item",
				"field_map": {"parent": "sales_order", "uom": "stock_uom", "name": "packed_item"},
				"condition": lambda item: get_remaining_packed_item_qty(item) > 0,
				"postprocess": update_item,
			},
			"Sales Order Item": {
				"doctype": "Material Request Item",
				"field_map": {
					"name": "sales_order_item",
					"parent": "sales_order",
					"delivery_date": "schedule_date",
					"bom_no": "bom_no",
				},
				"condition": lambda item: not frappe.db.exists(
					"Product Bundle", {"name": item.item_code, "disabled": 0}
				)
				and get_remaining_qty(item) > 0,
				"postprocess": update_item,
			},
		},
		target_doc,
		postprocess,
	)
	if doc and doc.items:
		return doc
	else:
		frappe.throw(_("Material Request already created for the ordered quantity"))


@frappe.whitelist()
def make_project(source_name, target_doc=None):
	def postprocess(source, doc):
		doc.project_type = "External"
		doc.project_name = source.name

	doc = get_mapped_doc(
		"Sales Order",
		source_name,
		{
			"Sales Order": {
				"doctype": "Project",
				"validation": {"docstatus": ["=", 1]},
				"field_map": {
					"name": "sales_order",
					"base_grand_total": "estimated_costing",
					"net_total": "total_sales_amount",
				},
			},
		},
		target_doc,
		postprocess,
	)

	return doc


@frappe.whitelist()
def make_delivery_note(source_name, target_doc=None, kwargs=None):
	from erpnext.stock.doctype.packed_item.packed_item import make_packing_list
	from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import (
		get_sre_details_for_voucher,
		get_sre_reserved_qty_details_for_voucher,
		get_ssb_bundle_for_voucher,
	)

	if not kwargs:
		kwargs = {
			"for_reserved_stock": frappe.flags.args and frappe.flags.args.for_reserved_stock,
			"skip_item_mapping": frappe.flags.args and frappe.flags.args.skip_item_mapping,
		}

	kwargs = frappe._dict(kwargs)

	sre_details = {}
	if kwargs.for_reserved_stock:
		sre_details = get_sre_reserved_qty_details_for_voucher("Sales Order", source_name)

	mapper = {
		"Sales Order": {"doctype": "Delivery Note", "validation": {"docstatus": ["=", 1]}},
		"Sales Taxes and Charges": {"doctype": "Sales Taxes and Charges", "reset_value": True},
		"Sales Team": {"doctype": "Sales Team", "add_if_empty": True},
	}

	# 0 qty is accepted, as the qty is uncertain for some items
	has_unit_price_items = frappe.db.get_value("Sales Order", source_name, "has_unit_price_items")

	def is_unit_price_row(source):
		return has_unit_price_items and source.qty == 0

	def select_item(d):
		filtered_items = kwargs.get("filtered_children", [])
		child_filter = d.name in filtered_items if filtered_items else True
		return child_filter

	def set_missing_values(source, target):
		if kwargs.get("ignore_pricing_rule"):
			# Skip pricing rule when the dn is creating from the pick list
			target.ignore_pricing_rule = 1

		target.run_method("set_missing_values")
		target.run_method("set_po_nos")
		target.run_method("calculate_taxes_and_totals")
		target.run_method("set_use_serial_batch_fields")

		if source.company_address:
			target.update({"company_address": source.company_address})
		else:
			# set company address
			target.update(get_company_address(target.company))

		if target.company_address:
			target.update(get_fetch_values("Delivery Note", "company_address", target.company_address))

		# if invoked in bulk creation, validations are ignored and thus this method is nerver invoked
		if frappe.flags.bulk_transaction:
			# set target items names to ensure proper linking with packed_items
			target.set_new_name()

		make_packing_list(target)

	def condition(doc):
		if doc.name in sre_details:
			del sre_details[doc.name]
			return False

		# make_mapped_doc sets js `args` into `frappe.flags.args`
		if frappe.flags.args and frappe.flags.args.delivery_dates:
			if cstr(doc.delivery_date) not in frappe.flags.args.delivery_dates:
				return False
		if frappe.flags.args and frappe.flags.args.until_delivery_date:
			if cstr(doc.delivery_date) > frappe.flags.args.until_delivery_date:
				return False

		return (
			(abs(doc.delivered_qty) < abs(doc.qty)) or is_unit_price_row(doc)
		) and doc.delivered_by_supplier != 1

	def update_item(source, target, source_parent):
		target.base_amount = (flt(source.qty) - flt(source.delivered_qty)) * flt(source.base_rate)
		target.amount = (flt(source.qty) - flt(source.delivered_qty)) * flt(source.rate)
		target.qty = (
			flt(source.qty) if is_unit_price_row(source) else flt(source.qty) - flt(source.delivered_qty)
		)

		item = get_item_defaults(target.item_code, source_parent.company)
		item_group = get_item_group_defaults(target.item_code, source_parent.company)

		if item:
			target.cost_center = (
				frappe.db.get_value("Project", source_parent.project, "cost_center")
				or item.get("buying_cost_center")
				or item_group.get("buying_cost_center")
			)

	if not kwargs.skip_item_mapping:
		mapper["Sales Order Item"] = {
			"doctype": "Delivery Note Item",
			"field_map": {
				"rate": "rate",
				"name": "so_detail",
				"parent": "against_sales_order",
			},
			"condition": lambda d: condition(d) and select_item(d),
			"postprocess": update_item,
		}

	so = frappe.get_doc("Sales Order", source_name)
	target_doc = get_mapped_doc("Sales Order", so.name, mapper, target_doc)

	if not kwargs.skip_item_mapping and kwargs.for_reserved_stock:
		sre_list = get_sre_details_for_voucher("Sales Order", source_name)

		if sre_list:

			def update_dn_item(source, target, source_parent):
				update_item(source, target, so)

			so_items = {d.name: d for d in so.items if d.stock_reserved_qty}

			for sre in sre_list:
				if not condition(so_items[sre.voucher_detail_no]):
					continue

				dn_item = get_mapped_doc(
					"Sales Order Item",
					sre.voucher_detail_no,
					{
						"Sales Order Item": {
							"doctype": "Delivery Note Item",
							"field_map": {
								"rate": "rate",
								"name": "so_detail",
								"parent": "against_sales_order",
							},
							"postprocess": update_dn_item,
						}
					},
					ignore_permissions=True,
				)

				dn_item.qty = flt(sre.reserved_qty) / flt(dn_item.get("conversion_factor", 1))
				dn_item.warehouse = sre.warehouse

				use_serial_batch_fields = frappe.get_single_value("Stock Settings", "use_serial_batch_fields")

				if (
					not use_serial_batch_fields
					and sre.reservation_based_on == "Serial and Batch"
					and (sre.has_serial_no or sre.has_batch_no)
				):
					dn_item.serial_and_batch_bundle = get_ssb_bundle_for_voucher(sre)

				target_doc.append("items", dn_item)
			else:
				# Correct rows index.
				for idx, item in enumerate(target_doc.items):
					item.idx = idx + 1

	if not kwargs.skip_item_mapping and frappe.flags.bulk_transaction and not target_doc.items:
		# the (date) condition filter resulted in an unintendedly created empty DN; remove it
		del target_doc
		return

	# Should be called after mapping items.
	set_missing_values(so, target_doc)

	return target_doc


@frappe.whitelist()
def make_sales_invoice(source_name, target_doc=None, ignore_permissions=False, args=None):
	if args is None:
		args = {}
	if isinstance(args, str):
		args = json.loads(args)

	# 0 qty is accepted, as the qty is uncertain for some items
	has_unit_price_items = frappe.db.get_value("Sales Order", source_name, "has_unit_price_items")

	def is_unit_price_row(source):
		return has_unit_price_items and source.qty == 0

	def postprocess(source, target):
		set_missing_values(source, target)
		# Get the advance paid Journal Entries in Sales Invoice Advance
		if target.get("allocate_advances_automatically"):
			target.set_advances()

	def set_missing_values(source, target):
		target.flags.ignore_permissions = True
		target.run_method("set_missing_values")
		target.run_method("set_po_nos")
		target.run_method("calculate_taxes_and_totals")
		target.run_method("set_use_serial_batch_fields")

		if source.company_address:
			target.update({"company_address": source.company_address})
		else:
			# set company address
			target.update(get_company_address(target.company))

		if target.company_address:
			target.update(get_fetch_values("Sales Invoice", "company_address", target.company_address))

		# set the redeem loyalty points if provided via shopping cart
		if source.loyalty_points and source.order_type == "Shopping Cart":
			target.redeem_loyalty_points = 1
			target.loyalty_points = source.loyalty_points

		target.debit_to = get_party_account("Customer", source.customer, source.company)

	def update_item(source, target, source_parent):
		def get_billed_qty(so_item_name):
			from frappe.query_builder.functions import Sum

			table = frappe.qb.DocType("Sales Invoice Item")
			query = (
				frappe.qb.from_(table)
				.select(Sum(table.qty).as_("qty"))
				.where((table.docstatus == 1) & (table.so_detail == so_item_name))
			)
			return query.run(pluck="qty")[0] or 0

		if source_parent.has_unit_price_items:
			# 0 Amount rows (as seen in Unit Price Items) should be mapped as it is
			pending_amount = flt(source.amount) - flt(source.billed_amt)
			target.amount = pending_amount if flt(source.amount) else 0
		else:
			target.amount = flt(source.amount) - flt(source.billed_amt)

		target.base_amount = target.amount * flt(source_parent.conversion_rate)
		target.qty = (
			source.qty - get_billed_qty(source.name)
			if (source.qty and source.billed_amt)
			else (source.qty if is_unit_price_row(source) else source.qty - source.returned_qty)
		)

		if source_parent.project:
			target.cost_center = frappe.db.get_value("Project", source_parent.project, "cost_center")
		if target.item_code:
			item = get_item_defaults(target.item_code, source_parent.company)
			item_group = get_item_group_defaults(target.item_code, source_parent.company)
			cost_center = item.get("selling_cost_center") or item_group.get("selling_cost_center")

			if cost_center:
				target.cost_center = cost_center

	def select_item(d):
		filtered_items = args.get("filtered_children", [])
		child_filter = d.name in filtered_items if filtered_items else True
		return child_filter

	def add_self_rm(doclist):
		parent = frappe.qb.DocType("Subcontracting Inward Order")
		child = frappe.qb.DocType("Subcontracting Inward Order Received Item")
		query = (
			frappe.qb.from_(parent)
			.join(child)
			.on(parent.name == child.parent)
			.select(
				child.required_qty,
				child.consumed_qty,
				child.billed_qty,
				child.rm_item_code,
				child.stock_uom,
				child.name,
			)
			.where(
				(parent.docstatus == 1)
				& (parent.sales_order == source_name)
				& (child.is_customer_provided_item == 0)
			)
		)
		result = query.run(as_dict=True)

		if result:
			idx = len(doclist.items) + 1
			for item in result:
				if (qty := max(item.required_qty, item.consumed_qty) - item.billed_qty) > 0:
					doclist.append(
						"items",
						{
							"item_code": item.rm_item_code,
							"qty": qty,
							"uom": item.stock_uom,
							"scio_detail": item.name,
						},
					)
					doclist.process_item_selection(idx)
					idx += 1
		doclist.has_subcontracted = 1

	doclist = get_mapped_doc(
		"Sales Order",
		source_name,
		{
			"Sales Order": {
				"doctype": "Sales Invoice",
				"field_map": {
					"party_account_currency": "party_account_currency",
				},
				"field_no_map": ["payment_terms_template"],
				"validation": {"docstatus": ["=", 1]},
			},
			"Sales Order Item": {
				"doctype": "Sales Invoice Item",
				"field_map": {
					"name": "so_detail",
					"parent": "sales_order",
				},
				"postprocess": update_item,
				"condition": lambda doc: (
					True
					if is_unit_price_row(doc)
					else (doc.qty and (doc.base_amount == 0 or abs(doc.billed_amt) < abs(doc.amount)))
				)
				and select_item(doc),
			},
			"Sales Taxes and Charges": {
				"doctype": "Sales Taxes and Charges",
				"reset_value": True,
			},
			"Sales Team": {"doctype": "Sales Team", "add_if_empty": True},
		},
		target_doc,
		postprocess,
		ignore_permissions=ignore_permissions,
	)

	if frappe.get_cached_value("Sales Order", source_name, "is_subcontracted"):
		add_self_rm(doclist)

	automatically_fetch_payment_terms = cint(
		frappe.get_single_value("Accounts Settings", "automatically_fetch_payment_terms")
	)
	if automatically_fetch_payment_terms:
		doclist.set_payment_schedule()

	return doclist


@frappe.whitelist()
def make_maintenance_schedule(source_name, target_doc=None):
	maint_schedule = frappe.db.sql(
		"""select t1.name
		from `tabMaintenance Schedule` t1, `tabMaintenance Schedule Item` t2
		where t2.parent=t1.name and t2.sales_order=%s and t1.docstatus=1""",
		source_name,
	)

	if not maint_schedule:
		doclist = get_mapped_doc(
			"Sales Order",
			source_name,
			{
				"Sales Order": {"doctype": "Maintenance Schedule", "validation": {"docstatus": ["=", 1]}},
				"Sales Order Item": {
					"doctype": "Maintenance Schedule Item",
					"field_map": {"parent": "sales_order"},
				},
			},
			target_doc,
		)

		return doclist


@frappe.whitelist()
def make_maintenance_visit(source_name, target_doc=None):
	visit = frappe.db.sql(
		"""select t1.name
		from `tabMaintenance Visit` t1, `tabMaintenance Visit Purpose` t2
		where t2.parent=t1.name and t2.prevdoc_docname=%s
		and t1.docstatus=1 and t1.completion_status='Fully Completed'""",
		source_name,
	)

	if not visit:
		doclist = get_mapped_doc(
			"Sales Order",
			source_name,
			{
				"Sales Order": {"doctype": "Maintenance Visit", "validation": {"docstatus": ["=", 1]}},
				"Sales Order Item": {
					"doctype": "Maintenance Visit Purpose",
					"field_map": {"parent": "prevdoc_docname", "parenttype": "prevdoc_doctype"},
				},
			},
			target_doc,
		)

		return doclist


@frappe.whitelist()
def get_events(start, end, filters=None):
	"""Returns events for Gantt / Calendar view rendering.

	:param start: Start date-time.
	:param end: End date-time.
	:param filters: Filters (JSON).
	"""
	from frappe.desk.calendar import get_event_conditions

	conditions = get_event_conditions("Sales Order", filters)

	data = frappe.db.sql(
		f"""
		select
			distinct `tabSales Order`.name, `tabSales Order`.customer_name, `tabSales Order`.status,
			`tabSales Order`.delivery_status, `tabSales Order`.billing_status,
			`tabSales Order Item`.delivery_date
		from
			`tabSales Order`, `tabSales Order Item`
		where `tabSales Order`.name = `tabSales Order Item`.parent
			and `tabSales Order`.skip_delivery_note = 0
			and (ifnull(`tabSales Order Item`.delivery_date, '0000-00-00')!= '0000-00-00') \
			and (`tabSales Order Item`.delivery_date between %(start)s and %(end)s)
			and `tabSales Order`.docstatus < 2
			{conditions}
		""",
		{"start": start, "end": end},
		as_dict=True,
		update={
			"allDay": 0,
			"convertToUserTz": 0,
		},
	)
	return data


@frappe.whitelist()
def make_purchase_order(source_name, selected_items=None, target_doc=None):
	"""Creates Purchase Order for each Supplier. Returns a list of doc objects."""

	from erpnext.setup.utils import get_exchange_rate

	if not selected_items:
		return

	if isinstance(selected_items, str):
		selected_items = json.loads(selected_items)

	def set_missing_values(source, target):
		target.supplier = supplier
		target.currency = frappe.db.get_value(
			"Supplier", filters={"name": supplier}, fieldname=["default_currency"]
		)
		company_currency = frappe.db.get_value(
			"Company", filters={"name": target.company}, fieldname=["default_currency"]
		)

		target.conversion_rate = get_exchange_rate(target.currency, company_currency, args="for_buying")

		target.apply_discount_on = ""
		target.additional_discount_percentage = 0.0
		target.discount_amount = 0.0
		target.inter_company_order_reference = ""
		target.shipping_rule = ""
		target.tc_name = ""
		target.terms = ""
		target.payment_terms_template = ""
		target.payment_schedule = []

		default_price_list = frappe.get_value("Supplier", supplier, "default_price_list")
		if default_price_list:
			target.buying_price_list = default_price_list

		default_payment_terms = frappe.get_value("Supplier", supplier, "payment_terms")
		if default_payment_terms:
			target.payment_terms_template = default_payment_terms

		if any(item.delivered_by_supplier == 1 for item in source.items):
			if source.shipping_address_name:
				target.shipping_address = source.shipping_address_name
				target.shipping_address_display = source.shipping_address
			else:
				target.shipping_address = source.customer_address
				target.shipping_address_display = source.address_display

			target.customer_contact_person = source.contact_person
			target.customer_contact_display = source.contact_display
			target.customer_contact_mobile = source.contact_mobile
			target.customer_contact_email = source.contact_email

		else:
			target.customer = ""
			target.customer_name = ""

		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	def update_item(source, target, source_parent):
		target.schedule_date = source.delivery_date
		target.qty = flt(source.qty) - (flt(source.ordered_qty) / flt(source.conversion_factor))
		target.stock_qty = flt(source.stock_qty) - flt(source.ordered_qty)
		target.project = source_parent.project

	def update_item_for_packed_item(source, target, _):
		target.qty = flt(source.qty) - flt(source.ordered_qty)

	def filter_items(item, supplier):
		if (
			item.ordered_qty < item.stock_qty
			and not is_product_bundle(item.item_code)
			and items_to_map.get(item.item_code) == supplier
		):
			return True

		return False

	items_to_map = {
		item.get("item_code"): item.get("supplier") for item in selected_items if item.get("item_code")
	}
	item_codes = list(set(items_to_map.keys()))
	suppliers = list(set(items_to_map.values()))

	if not suppliers:
		suppliers = [None]

	purchase_orders = []
	for supplier in suppliers:
		doc = get_mapped_doc(
			"Sales Order",
			source_name,
			{
				"Sales Order": {
					"doctype": "Purchase Order",
					"field_no_map": [
						"address_display",
						"contact_display",
						"contact_mobile",
						"contact_email",
						"contact_person",
						"taxes_and_charges",
						"shipping_address",
						"dispatch_address",
					],
					"validation": {"docstatus": ["=", 1]},
				},
				"Sales Order Item": {
					"doctype": "Purchase Order Item",
					"field_map": [
						["name", "sales_order_item"],
						["parent", "sales_order"],
						["stock_uom", "stock_uom"],
						["uom", "uom"],
						["conversion_factor", "conversion_factor"],
						["delivery_date", "schedule_date"],
					],
					"field_no_map": [
						"rate",
						"price_list_rate",
						"item_tax_template",
						"discount_percentage",
						"discount_amount",
						"pricing_rules",
						"margin_type",
						"margin_rate_or_amount",
					],
					"postprocess": update_item,
					"condition": lambda doc, s=supplier: filter_items(doc, s),
				},
				"Packed Item": {
					"doctype": "Purchase Order Item",
					"field_map": [
						["name", "sales_order_packed_item"],
						["parent", "sales_order"],
						["uom", "uom"],
						["conversion_factor", "conversion_factor"],
						["parent_item", "product_bundle"],
						["rate", "rate"],
					],
					"field_no_map": [
						"price_list_rate",
						"item_tax_template",
						"discount_percentage",
						"discount_amount",
						"supplier",
						"pricing_rules",
					],
					"postprocess": update_item_for_packed_item,
					"condition": lambda doc: doc.parent_item in item_codes
					and flt(doc.ordered_qty) < flt(doc.qty),
				},
			},
			target_doc,
			set_missing_values,
		)

		set_delivery_date(doc.items, source_name)
		if doc.supplier:
			doc.insert()
		purchase_orders.append(doc)

	return purchase_orders


def set_delivery_date(items, sales_order):
	delivery_dates = frappe.get_all(
		"Sales Order Item", filters={"parent": sales_order}, fields=["delivery_date", "item_code"]
	)

	delivery_by_item = frappe._dict()
	for date in delivery_dates:
		delivery_by_item[date.item_code] = date.delivery_date

	for item in items:
		if item.product_bundle:
			item.schedule_date = delivery_by_item[item.product_bundle]


def is_product_bundle(item_code):
	return frappe.db.exists("Product Bundle", {"name": item_code, "disabled": 0})


@frappe.whitelist()
def make_work_orders(items, sales_order, company, project=None):
	"""Make Work Orders against the given Sales Order for the given `items`"""
	items = json.loads(items).get("items")
	out = []

	for i in items:
		if not i.get("bom"):
			frappe.throw(_("Please select BOM against item {0}").format(i.get("item_code")))
		if not i.get("pending_qty"):
			frappe.throw(_("Please select Qty against item {0}").format(i.get("item_code")))

		work_order = frappe.get_doc(
			doctype="Work Order",
			production_item=i["item_code"],
			bom_no=i.get("bom"),
			qty=i["pending_qty"],
			company=company,
			sales_order=sales_order,
			sales_order_item=i["sales_order_item"],
			project=project,
			fg_warehouse=i["warehouse"],
			description=i["description"],
		).insert()
		work_order.set_work_order_operations()
		work_order.flags.ignore_mandatory = True
		work_order.save()
		out.append(work_order)

	return [p.name for p in out]


@frappe.whitelist()
def update_status(status, name):
	so = frappe.get_doc("Sales Order", name, check_permission="submit")
	so.update_status(status)


@frappe.whitelist()
def make_raw_material_request(items, company, sales_order, project=None):
	if not frappe.has_permission("Sales Order", "write"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	if isinstance(items, str):
		items = frappe._dict(json.loads(items))

	for item in items.get("items"):
		item["include_exploded_items"] = items.get("include_exploded_items")
		item["ignore_existing_ordered_qty"] = items.get("ignore_existing_ordered_qty")
		item["include_raw_materials_from_sales_order"] = items.get("include_raw_materials_from_sales_order")

	items.update({"company": company, "sales_order": sales_order})

	item_wh = {}
	for item in items.get("items"):
		if item.get("warehouse"):
			item_wh[item.get("item_code")] = item.get("warehouse")

	raw_materials = get_items_for_material_requests(items)
	if not raw_materials:
		frappe.msgprint(_("Material Request not created, as quantity for Raw Materials already available."))
		return

	material_request = frappe.new_doc("Material Request")
	material_request.update(
		dict(
			doctype="Material Request",
			transaction_date=nowdate(),
			company=company,
			material_request_type="Purchase",
		)
	)
	for item in raw_materials:
		item_doc = frappe.get_cached_doc("Item", item.get("item_code"))

		schedule_date = add_days(nowdate(), cint(item_doc.lead_time_days))
		row = material_request.append(
			"items",
			{
				"item_code": item.get("item_code"),
				"qty": item.get("quantity"),
				"schedule_date": schedule_date,
				"warehouse": item_wh.get(item.get("main_bom_item")) or item.get("warehouse"),
				"sales_order": sales_order,
				"project": project,
			},
		)

		if not (strip_html(item.get("description")) and strip_html(item_doc.description)):
			row.description = item_doc.item_name or item.get("item_code")

	material_request.insert()
	material_request.flags.ignore_permissions = 1
	material_request.run_method("set_missing_values")
	material_request.submit()
	return material_request


@frappe.whitelist()
def make_inter_company_purchase_order(source_name, target_doc=None):
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_inter_company_transaction

	return make_inter_company_transaction("Sales Order", source_name, target_doc)


@frappe.whitelist()
def create_pick_list(source_name, target_doc=None):
	from erpnext.stock.doctype.packed_item.packed_item import is_product_bundle

	def validate_sales_order():
		so = frappe.get_doc("Sales Order", source_name)
		for item in so.items:
			if item.stock_reserved_qty > 0:
				frappe.throw(
					_(
						"Cannot create a pick list for Sales Order {0} because it has reserved stock. Please unreserve the stock in order to create a pick list."
					).format(frappe.bold(source_name))
				)

	def update_item_quantity(source, target, source_parent) -> None:
		picked_qty = flt(source.picked_qty) / (flt(source.conversion_factor) or 1)
		qty_to_be_picked = flt(source.qty) - max(picked_qty, flt(source.delivered_qty))

		target.qty = qty_to_be_picked
		target.stock_qty = qty_to_be_picked * flt(source.conversion_factor)

		# update available qty
		bin_details = get_bin_details(source.item_code, source.warehouse, source_parent.company)
		target.actual_qty = bin_details.get("actual_qty")
		target.company_total_stock = bin_details.get("company_total_stock")

	def update_packed_item_qty(source, target, source_parent) -> None:
		qty = flt(source.qty)
		for item in source_parent.items:
			if source.parent_detail_docname == item.name:
				picked_qty = flt(item.picked_qty) / (flt(item.conversion_factor) or 1)
				pending_percent = (item.qty - max(picked_qty, item.delivered_qty)) / item.qty
				target.qty = target.stock_qty = qty * pending_percent
				return

	def should_pick_order_item(item) -> bool:
		return (
			abs(item.delivered_qty) < abs(item.qty)
			and item.delivered_by_supplier != 1
			and not is_product_bundle(item.item_code)
		)

	# Don't allow a Pick List to be created against a Sales Order that has reserved stock.
	validate_sales_order()

	doc = get_mapped_doc(
		"Sales Order",
		source_name,
		{
			"Sales Order": {
				"doctype": "Pick List",
				"field_map": {"set_warehouse": "parent_warehouse"},
				"validation": {"docstatus": ["=", 1]},
			},
			"Sales Order Item": {
				"doctype": "Pick List Item",
				"field_map": {"parent": "sales_order", "name": "sales_order_item"},
				"postprocess": update_item_quantity,
				"condition": should_pick_order_item,
			},
			"Packed Item": {
				"doctype": "Pick List Item",
				"field_map": {
					"parent": "sales_order",
					"parent_detail_docname": "sales_order_item",
					"name": "product_bundle_item",
				},
				"field_no_map": ["picked_qty"],
				"postprocess": update_packed_item_qty,
			},
		},
		target_doc,
	)

	doc.purpose = "Delivery"

	doc.set_item_locations()

	return doc


def update_produced_qty_in_so_item(sales_order, sales_order_item):
	# for multiple work orders against same sales order item
	linked_wo_with_so_item = frappe.db.get_all(
		"Work Order",
		["produced_qty"],
		{"sales_order_item": sales_order_item, "sales_order": sales_order, "docstatus": 1},
	)

	total_produced_qty = 0
	for wo in linked_wo_with_so_item:
		total_produced_qty += flt(wo.get("produced_qty"))

	if not total_produced_qty and frappe.flags.in_patch:
		return

	frappe.db.set_value("Sales Order Item", sales_order_item, "produced_qty", total_produced_qty)


@frappe.whitelist()
def get_work_order_items(sales_order, for_raw_material_request=0):
	"""Returns items with BOM that already do not have a linked work order"""
	if sales_order:
		so = frappe.get_doc("Sales Order", sales_order)

		wo = qb.DocType("Work Order")

		items = []
		item_codes = [i.item_code for i in so.items]
		product_bundle_parents = [
			pb.new_item_code
			for pb in frappe.get_all(
				"Product Bundle", {"new_item_code": ["in", item_codes], "disabled": 0}, ["new_item_code"]
			)
		]

		overproduction_percentage_for_sales_order = (
			frappe.get_single_value("Manufacturing Settings", "overproduction_percentage_for_sales_order")
			/ 100
		)
		for table in [so.items, so.packed_items]:
			for i in table:
				bom = get_default_bom(i.item_code)
				stock_qty = i.qty if i.doctype == "Packed Item" else i.stock_qty

				if not for_raw_material_request:
					total_work_order_qty = flt(
						qb.from_(wo)
						.select(Sum(wo.qty - wo.process_loss_qty))
						.where(
							(wo.production_item == i.item_code)
							& (wo.sales_order == so.name)
							& (wo.sales_order_item == i.name)
							& (wo.docstatus == 1)
							& (wo.status != "Closed")
						)
						.run()[0][0]
					)
					pending_qty = stock_qty - total_work_order_qty
				else:
					pending_qty = stock_qty

				if not pending_qty:
					pending_qty = stock_qty * overproduction_percentage_for_sales_order

				if pending_qty > 0 and i.item_code not in product_bundle_parents:
					items.append(
						dict(
							name=i.name,
							item_code=i.item_code,
							item_name=i.item_name,
							description=i.description,
							bom=bom or "",
							warehouse=i.warehouse,
							pending_qty=pending_qty,
							required_qty=pending_qty if for_raw_material_request else 0,
							sales_order_item=i.name,
						)
					)

		return items


@frappe.whitelist()
def get_stock_reservation_status():
	return frappe.db.get_single_value("Stock Settings", "enable_stock_reservation")

@frappe.whitelist()
def larksuite_notification(sales_order_doc):
    sales_order = json.loads(sales_order_doc)

    # Validate sensitive coupons before sending to Lark
    doc = frappe.get_doc("Sales Order", sales_order.get("name"))
    doc.validate_sensitive_coupons()

    url = f"{config.FN_BASE_URL}/api/erp/sales_orders/{sales_order.get('name')}/notifications"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.FN_BEARER_TOKEN}",
    }

    try:
        response = requests.post(url=url, headers=headers, data=sales_order_doc)

        response.raise_for_status()

        try:
            return response.json().get("message", "Success")
        except json.JSONDecodeError:
            return response.text

    except requests.exceptions.HTTPError:
        error_message = f"Error ({response.status_code}): {response.text}"
        return error_message

    except Exception as e:
        return str(e)

@frappe.whitelist()
def get_split_orders_in_group(split_order_group, include_cancelled=False):
	"""
	Get all orders in a split order group

	Args:
		split_order_group: The split order group ID
		include_cancelled: Whether to include cancelled orders

	Returns:
		List of orders in the group with details
	"""
	if not split_order_group:
		return []

	filters = {
		"split_order_group": split_order_group,
		"is_split_order": 1
	}

	if not include_cancelled:
		filters["cancelled_status"] = "Uncancelled"

	orders = frappe.get_all("Sales Order",
		filters=filters,
		fields=[
			"name", "order_number", "customer", "customer_name",
			"grand_total", "currency", "haravan_order_id",
			"cancelled_status", "financial_status", "fulfillment_status",
			"transaction_date", "modified"
		],
		order_by="transaction_date asc"
	)
	for order in orders:
		order["is_original_order"] = (order.get("haravan_order_id") == split_order_group)

	return orders

@frappe.whitelist()
def make_subcontracting_inward_order(source_name, target_doc=None):
	if not is_so_fully_subcontracted(source_name):
		return get_mapped_subcontracting_inward_order(source_name, target_doc)
	else:
		frappe.throw(_("This Sales Order has been fully subcontracted."))


def is_so_fully_subcontracted(so_name):
	table = frappe.qb.DocType("Sales Order Item")
	query = (
		frappe.qb.from_(table)
		.select(table.name)
		.where((table.parent == so_name) & (table.qty != table.subcontracted_qty))
	)
	return not query.run(as_dict=True)


def get_mapped_subcontracting_inward_order(source_name, target_doc=None):
	def post_process(source_doc, target_doc):
		if (
			frappe.db.count(
				"Warehouse", {"customer": source_doc.customer, "disabled": 0, "is_rejected_warehouse": 0}
			)
			== 1
		):
			target_doc.customer_warehouse = frappe.get_cached_value(
				"Warehouse",
				{"customer": source_doc.customer, "disabled": 0, "is_rejected_warehouse": 0},
				"name",
			)
		target_doc.populate_items_table()

	if target_doc and isinstance(target_doc, str):
		target_doc = json.loads(target_doc)
		for key in ["service_items", "items", "received_items"]:
			if key in target_doc:
				del target_doc[key]
		target_doc = json.dumps(target_doc)

	target_doc = get_mapped_doc(
		"Sales Order",
		source_name,
		{
			"Sales Order": {
				"doctype": "Subcontracting Inward Order",
				"field_map": {},
				"field_no_map": ["total_qty", "total", "net_total"],
				"validation": {
					"docstatus": ["=", 1],
				},
			},
			"Sales Order Item": {
				"doctype": "Subcontracting Inward Order Service Item",
				"field_map": {
					"name": "sales_order_item",
				},
				"field_no_map": ["qty", "fg_item_qty", "amount"],
				"condition": lambda item: item.qty != item.subcontracted_qty,
			},
		},
		target_doc,
		post_process,
	)

	return target_doc

def _tokenize_serials(s):
	return {t.strip() for t in str(s).replace("\n", ",").split(",") if t.strip()}


def _update_sales_order_return_amount(sales_order):
	"""
	Recalculate and update the return_amount for the sales order based on linked buyback items.
	Logic: Sum of (buyback_price IF exists ELSE calculated_buyback_price)
	"""
	if not sales_order:
		return

	buyback_items = frappe.get_all(
		"Buyback Exchange Item",
		filters={"current_sales_order": sales_order},
		fields=["buyback_price", "calculated_buyback_price"],
	)

	total_return_amount = 0.0
	for item in buyback_items:
		if item.buyback_price is not None and flt(item.buyback_price) > 0:
			price = flt(item.buyback_price)
		else:
			price = flt(item.calculated_buyback_price)
		total_return_amount += price

	frappe.db.set_value("Sales Order", sales_order, "return_amount", total_return_amount)
	return total_return_amount


@frappe.whitelist()
def get_buyback_items(sales_order):
	return frappe.get_list("Buyback Exchange Item",
		filters={"current_sales_order": sales_order},
		fields=["product_name", "item_code", "buyback_price", "parent", "order_code", "prev_sales_order", "name", "buyback_percentage", "calculated_buyback_price", "sale_price"],
		ignore_permissions=True
	)

@frappe.whitelist()
def get_available_buyback_items(phone=None):
	"""Get all available buyback items that are not yet linked to any sales order.
	Filters by phone number if provided.
	"""
	query = """
		SELECT i.name, i.product_name, i.item_code, i.buyback_price, i.parent, i.sale_price, i.buyback_percentage, i.order_code, i.prev_sales_order
		FROM `tabBuyback Exchange Item` i
		JOIN `tabBuyback Exchange` p ON i.parent = p.name
		WHERE i.current_sales_order IS NULL
	"""
	params = {}
	if phone:
		query += " AND p.phone_number LIKE %(phone)s"
		params["phone"] = f"%{phone}%"

	query += " ORDER BY i.creation DESC LIMIT 100"

	return frappe.db.sql(query, params, as_dict=True)

@frappe.whitelist()
def link_buyback_items(sales_order, item_names):
	"""Link selected buyback items to the current sales order."""
	import json

	if isinstance(item_names, str):
		item_names = json.loads(item_names)

	if not item_names:
		frappe.throw(_("No items selected"))

	updated_count = 0
	for item_name in item_names:
		try:
			frappe.db.set_value("Buyback Exchange Item", item_name, "current_sales_order", sales_order)
			updated_count += 1
		except Exception as e:
			frappe.log_error(f"Failed to link buyback item {item_name}: {e!s}")

	if not updated_count:
		return {
			"success": False,
			"message": _("No buyback items were updated"),
			"count": 0
		}

	# Update total return amount on the Sales Order
	new_total = _update_sales_order_return_amount(sales_order)

	return {
		"success": True,
		"message": f"Successfully linked {updated_count} buyback item(s)",
		"count": updated_count,
		"return_amount": new_total
	}

@frappe.whitelist()
def unlink_buyback_item(item_name):
	"""Unlink a buyback item from the current sales order."""
	current_so = frappe.db.get_value("Buyback Exchange Item", item_name, "current_sales_order")

	frappe.db.set_value("Buyback Exchange Item", item_name, "current_sales_order", None)

	new_total = 0.0
	if current_so:
		new_total = _update_sales_order_return_amount(current_so)

	return {
		"success": True,
		"message": "Buyback item unlinked successfully",
		"return_amount": new_total
	}

@frappe.whitelist()
def get_item_promotions_by_serial(source_order, target_serial):
	"""Fetch promotion fields for a specific serial number from a source Sales Order."""
	if not source_order or not target_serial:
		return {}

	order_data = frappe.db.get_value(
		"Sales Order",
		source_order,
		["haravan_ref_order_id", "split_order_group", "is_split_order"]
	)
	if not order_data:
		return {}

	haravan_ref_order_id, split_group, is_split = order_data

	ref_names = get_candidate_reference_orders(
		source_order=source_order,
		haravan_ref_order_id=haravan_ref_order_id,
		split_order_group=split_group,
		is_split_order=is_split
	)
	if not ref_names:
		return {}

	item = frappe.db.get_value(
		"Sales Order Item",
		{"parent": ["in", ref_names], "serial_numbers": ["like", f"%{target_serial}%"]},
		["new_promotions", "promotion_1", "promotion_2", "promotion_3", "promotion_4", "promotion_5"],
		as_dict=True
	)

	return item or {}


@frappe.whitelist()
def validate_serial_number(serial_number, sales_order_name=None):
	"""
	Checks if a serial number is used in an unrelated order.
	"""
	if not serial_number:
		return {"allowed": True}

	related_orders = set()
	if sales_order_name and frappe.db.exists("Sales Order", sales_order_name):
		so = frappe.get_doc("Sales Order", sales_order_name)
		related_orders = set(so.get_all_related_sales_orders() or [])

	duplicate_items = frappe.db.sql("""
		SELECT 
			so_item.parent as order_name,
			so_item.serial_numbers
		FROM 
			`tabSales Order Item` so_item
		INNER JOIN
			`tabSales Order` so ON so.name = so_item.parent
		WHERE 
			so_item.serial_numbers LIKE %s
			AND so.docstatus < 2
			AND so.name != %s
	""", (f"%{serial_number}%", sales_order_name or ""), as_dict=True)

	for d in duplicate_items:
		d_serials = [s.strip() for s in (d.serial_numbers or "").split("\n") if s.strip()]
		if serial_number in d_serials:
			if d.order_name not in related_orders:
				return {
					"allowed": False,
					"duplicate_order": d.order_name
				}

	return {"allowed": True}

def get_candidate_reference_orders(source_order=None, haravan_ref_order_id=None, split_order_group=None, is_split_order=False):
	"""
	given a sales order, find all ref sales orders of sibling orders in one group
	"""
	reference_ids = set()

	if haravan_ref_order_id:
		reference_ids.add(haravan_ref_order_id)

	if is_split_order and split_order_group and source_order:
		sibling_orders = frappe.db.get_all(
			"Sales Order",
			filters={
				"split_order_group": split_order_group,
				"name": ["!=", source_order],
				"cancelled_status": "Uncancelled"
			},
			fields=["haravan_ref_order_id"]
		)
		for sibling in sibling_orders:
			if sibling.haravan_ref_order_id:
				reference_ids.add(sibling.haravan_ref_order_id)

	if not reference_ids:
		return []

	original_sales_orders = frappe.db.get_all(
		"Sales Order",
		filters={
			"haravan_order_id": ["in", list(reference_ids)],
			"cancelled_status": "Uncancelled"
		},
		fields=["name"]
	)

	return [order.name for order in original_sales_orders]
