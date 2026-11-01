# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from erpnext.selling.doctype.sales_order.item_utils import (
	SKU_PREFIX_TEMPORARY_JEWELRY,
	is_serial_match_jewelry_item,
)

MAX_REFERENCE_DEPTH = 10

RULE_VARIANT = "variant_id"
RULE_TEMPORARY_TO_REAL = "temporary_to_real"

REF_ITEM_FIELDS = [
	"name",
	"parent",
	"sku",
	"item_name",
	"type",
	"haravan_variant_id",
	"serial_numbers",
	"price_list_rate",
	"rate",
]


def get_candidate_reference_orders(order):
	"""
	Reference orders of `order` and of the other member orders in its split group.
	`order` is any object with haravan_ref_order_id, is_split_order and split_order_group.
	"""
	reference_ids = set()

	if order.haravan_ref_order_id:
		reference_ids.add(order.haravan_ref_order_id)

	if order.is_split_order and order.split_order_group:
		sibling_orders = frappe.db.get_all(
			"Sales Order",
			filters={"split_order_group": order.split_order_group},
			fields=["haravan_ref_order_id"],
		)
		for sibling in sibling_orders:
			if sibling.haravan_ref_order_id:
				reference_ids.add(sibling.haravan_ref_order_id)

	if not reference_ids:
		return []

	original_sales_orders = frappe.db.get_all(
		"Sales Order", filters={"haravan_order_id": ["in", list(reference_ids)]}, fields=["name"]
	)

	return [o.name for o in original_sales_orders]


def get_reference_chain_levels(sales_order, max_depth=MAX_REFERENCE_DEPTH):
	"""
	Walk the reference chain up to `max_depth` levels.
	Level 1 is sales_order.get_candidate_reference_orders(); each next level holds the
	candidate reference orders of the previous one. Returns a list of levels (lists of names),
	nearest first. Every order appears once, so cycles stop.
	"""
	seen = {sales_order.name}
	levels = []
	current = [n for n in sales_order.get_candidate_reference_orders() if n not in seen]

	while current and len(levels) < max_depth:
		current = list(dict.fromkeys(current))
		seen.update(current)
		levels.append(current)

		orders = frappe.db.get_all(
			"Sales Order",
			filters={"name": ["in", current]},
			fields=["name", "haravan_ref_order_id", "is_split_order", "split_order_group"],
		)
		next_level = []
		for order in orders:
			next_level += [n for n in get_candidate_reference_orders(order) if n not in seen]
		current = next_level

	return levels


def is_temporary_item(item):
	return str(getattr(item, "sku", "") or "").startswith(SKU_PREFIX_TEMPORARY_JEWELRY)


def _price(item):
	return flt(getattr(item, "price_list_rate", None) or getattr(item, "rate", None))


def _product_type(item):
	return str(getattr(item, "type", "") or "").strip().lower()


def _norm(value):
	return str(value).strip() if value not in (None, "") else None


def _serial(item):
	return str(getattr(item, "serial_numbers", "") or "").strip()


def is_temporary_to_real_match(current_item, ref_item):
	"""A temporary product (SPT) became the real product: same price and same product type."""
	if is_temporary_item(current_item) or not is_temporary_item(ref_item):
		return False
	price = _price(current_item)
	product_type = _product_type(current_item)
	return bool(
		price and product_type and price == _price(ref_item) and product_type == _product_type(ref_item)
	)


def match_missing_serials(missing_items, ref_levels, is_serial_allowed):
	"""
	Find a serial for each item in `missing_items` from the reference chain.

	ref_levels: list of lists of reference items, nearest level first.
	is_serial_allowed(serial) -> bool: rejects serials used elsewhere.

	Rules, in order (the first rule that gives a serial wins, nearest level first):
	1. Same Haravan Variant ID.
	2. A temporary product (SPT) with the same price and product type.

	An item is skipped when the nearest level for a rule offers more than one serial, and a serial
	is only given out when exactly one item claims it.
	Returns {current_item.name: (serial, ref_item, rule)}.
	"""
	rules = (
		(
			RULE_VARIANT,
			lambda cur, ref: _norm(getattr(cur, "haravan_variant_id", None))
			and _norm(getattr(cur, "haravan_variant_id", None))
			== _norm(getattr(ref, "haravan_variant_id", None)),
		),
		(RULE_TEMPORARY_TO_REAL, is_temporary_to_real_match),
	)

	claims = {}
	for item in missing_items:
		claim = _find_claim(item, ref_levels, rules, is_serial_allowed)
		if claim:
			claims[item.name] = claim

	claimed_count = {}
	for serial, _ref, _rule in claims.values():
		claimed_count[serial] = claimed_count.get(serial, 0) + 1

	return {name: claim for name, claim in claims.items() if claimed_count[claim[0]] == 1}


def _find_claim(item, ref_levels, rules, is_serial_allowed):
	for rule, matches in rules:
		for level in ref_levels:
			found = {}
			for ref in level:
				serial = _serial(ref)
				if serial and matches(item, ref):
					found.setdefault(serial, ref)
			if not found:
				continue
			if len(found) > 1:
				return None
			serial, ref = next(iter(found.items()))
			return (serial, ref, rule) if is_serial_allowed(serial) else None
	return None


def backfill_missing_serials(sales_order):
	"""
	Fill empty serial_numbers on jewelry items from the full reference chain.
	Only writes items that are still empty; never overwrites a serial.
	"""
	if sales_order.docstatus == 2 or sales_order.get("cancelled_status") == "Cancelled":
		return {}

	missing_items = [
		item
		for item in (sales_order.get("items") or [])
		if is_serial_match_jewelry_item(item) and not _serial(item)
	]
	if not missing_items:
		return {}

	levels = get_reference_chain_levels(sales_order)
	if not levels:
		return {}

	ref_items = frappe.db.get_all(
		"Sales Order Item",
		filters={"parenttype": "Sales Order", "parent": ["in", [n for level in levels for n in level]]},
		fields=REF_ITEM_FIELDS,
		order_by="idx asc",
	)
	items_by_parent = {}
	for ref in ref_items:
		items_by_parent.setdefault(ref.parent, []).append(ref)
	ref_levels = [[ref for name in level for ref in items_by_parent.get(name, [])] for level in levels]

	from erpnext.selling.doctype.sales_order.sales_order import _tokenize_serials, validate_serial_number

	serials_on_order = set()
	for item in sales_order.get("items") or []:
		serials_on_order |= _tokenize_serials(_serial(item)) if _serial(item) else set()

	def is_serial_allowed(serial):
		tokens = _tokenize_serials(serial)
		if not tokens or tokens & serials_on_order:
			return False
		return all(validate_serial_number(token, sales_order.name).get("allowed") for token in tokens)

	matches = match_missing_serials(missing_items, ref_levels, is_serial_allowed)
	for item in missing_items:
		if item.name in matches:
			item.db_set("serial_numbers", matches[item.name][0])

	return matches
