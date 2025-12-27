# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe.model.document import Document


class SalesOrderItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		actual_qty: DF.Float
		additional_notes: DF.Text | None
		against_blanket_order: DF.Check
		amount: DF.Currency
		barcode: DF.Data | None
		base_amount: DF.Currency
		base_net_amount: DF.Currency
		base_net_rate: DF.Currency
		base_price_list_rate: DF.Currency
		base_rate: DF.Currency
		base_rate_with_margin: DF.Currency
		billed_amt: DF.Currency
		blanket_order: DF.Link | None
		blanket_order_rate: DF.Currency
		bom_no: DF.Link | None
		brand: DF.Link | None
		company_total_stock: DF.Float
		conversion_factor: DF.Float
		cost_center: DF.Link | None
		customer_item_code: DF.Data | None
		delivered_by_supplier: DF.Check
		delivered_qty: DF.Float
		delivery_date: DF.Date | None
		description: DF.TextEditor | None
		diamond_details: DF.Data | None
		discount_amount: DF.Currency
		discount_percentage: DF.Percent
		discount_rate: DF.Data | None
		distributed_discount_amount: DF.Currency
		ensure_delivery_based_on_produced_serial_no: DF.Check
		grant_commission: DF.Check
		gross_profit: DF.Currency
		haravan_variant_id: DF.Int
		image: DF.Attach | None
		is_free_item: DF.Check
		is_policy_locked: DF.Check
		is_stock_item: DF.Check
		item_code: DF.Link | None
		item_group: DF.Link | None
		item_name: DF.Data
		item_policy: DF.LongText | None
		item_tax_rate: DF.Code | None
		item_tax_template: DF.Link | None
		margin_rate_or_amount: DF.Float
		margin_type: DF.Literal["", "Percentage", "Amount"]
		material_request: DF.Link | None
		material_request_item: DF.Data | None
		net_amount: DF.Currency
		net_rate: DF.Currency
		ordered_qty: DF.Float
		page_break: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		picked_qty: DF.Float
		planned_qty: DF.Float
		prevdoc_docname: DF.Link | None
		price_list_rate: DF.Currency
		pricing_rules: DF.SmallText | None
		produced_qty: DF.Float
		product_availability_status: DF.Literal["", "In Stock", "Pre-order"]
		product_details: DF.Data | None
		production_plan_qty: DF.Float
		project: DF.Link | None
		projected_qty: DF.Float
		promotion: DF.Link | None
		promotion_1: DF.Link | None
		promotion_2: DF.Link | None
		promotion_3: DF.Link | None
		promotion_4: DF.Link | None
		promotion_5: DF.Link | None
		purchase_order: DF.Link | None
		purchase_order_item: DF.Data | None
		qty: DF.Float
		quotation_item: DF.Data | None
		rate: DF.Currency
		rate_with_margin: DF.Currency
		reserve_stock: DF.Check
		returned_qty: DF.Float
		serial: DF.Link | None
		serial_numbers: DF.SmallText | None
		sku: DF.Data | None
		stock_qty: DF.Float
		stock_reserved_qty: DF.Float
		stock_uom: DF.Link | None
		stock_uom_rate: DF.Currency
		supplier: DF.Link | None
		target_warehouse: DF.Link | None
		total_weight: DF.Float
		transaction_date: DF.Date | None
		type: DF.Data | None
		uom: DF.Link | None
		valuation_rate: DF.Currency
		variant_title: DF.Data | None
		warehouse: DF.Link | None
		weight_per_unit: DF.Float
		weight_uom: DF.Link | None
		work_order_qty: DF.Float
	# end: auto-generated types

	pass


def on_doctype_update():
	frappe.db.add_index("Sales Order Item", ["item_code", "warehouse"])


@frappe.whitelist()
def trigger_manual_webhook(item_name):
	"""
	Trigger manual sync webhook for a Sales Order Item.
	Doesn't save the document, just finds and fires the configured webhooks.
	"""
	from frappe.integrations.doctype.webhook import get_all_webhooks
	from frappe.integrations.doctype.webhook.webhook import get_context
	
	doc = frappe.get_doc("Sales Order Item", item_name)
	
	# Ge webhooks from DB
	webhooks = frappe.cache.get_value("webhooks", get_all_webhooks)
	webhooks_for_doc = webhooks.get(doc.doctype, [])
	
	if not webhooks_for_doc:
		frappe.msgprint(frappe._("Chưa cấu hình Webhook cho {0}").format(doc.doctype))
		return False

	triggered = False
	# Check "on_update" events
	for webhook in webhooks_for_doc:
		if webhook.get("webhook_docevent") != "on_update":
			continue
			
		trigger_webhook = False
		# Check conditions
		if not webhook.get("condition"):
			trigger_webhook = True
		elif frappe.safe_eval(webhook.get("condition"), eval_locals=get_context(doc)):
			trigger_webhook = True
				
		if trigger_webhook:
			triggered = True
			frappe.enqueue(
				"frappe.integrations.doctype.webhook.webhook.enqueue_webhook",
				doc_doctype=doc.doctype,
				doc_name=doc.name,
				webhook=webhook,
				queue=webhook.get("background_jobs_queue") or "default",
				now=frappe.flags.in_test
			)
	
	if not triggered:
		frappe.msgprint(frappe._("Chính sách đã được điền"))
		return False
		
	return True
