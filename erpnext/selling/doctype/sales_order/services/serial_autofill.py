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
	return get_candidate_reference_orders_for([order])


def get_candidate_reference_orders_for(orders):
	"""
	Candidate reference orders of several orders at once (at most 2 queries).
	Same result as joining get_candidate_reference_orders() of each order.
	"""
	reference_ids = {o.haravan_ref_order_id for o in orders if o.haravan_ref_order_id}
	split_groups = {o.split_order_group for o in orders if o.is_split_order and o.split_order_group}

	if split_groups:
		sibling_orders = frappe.db.get_all(
			"Sales Order",
			filters={"split_order_group": ["in", list(split_groups)]},
			fields=["haravan_ref_order_id"],
		)
		reference_ids.update(s.haravan_ref_order_id for s in sibling_orders if s.haravan_ref_order_id)

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
	nearest first. Every order appears once, so cycles stop. At most 3 queries per level.
	"""
	seen = {sales_order.name}
	levels = []
	current = [n for n in sales_order.get_candidate_reference_orders() if n not in seen]

	while current and len(levels) < max_depth:
		current = list(dict.fromkeys(current))
		seen.update(current)
		levels.append(current)

		if len(levels) == max_depth:
			break

		orders = frappe.db.get_all(
			"Sales Order",
			filters={"name": ["in", current]},
			fields=["name", "haravan_ref_order_id", "is_split_order", "split_order_group"],
		)
		current = [n for n in get_candidate_reference_orders_for(orders) if n not in seen]

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


def get_serials_used_elsewhere(serials, sales_order_name=None, related_orders=()):
	"""
	One query for many serials. Returns {serial: order_name} for each serial found on another
	uncancelled order that is not in `related_orders` (same rule as validate_serial_number).
	"""
	serials = [s for s in dict.fromkeys(serials) if s]
	if not serials:
		return {}

	like_conditions = " OR ".join(["so_item.serial_numbers LIKE %s"] * len(serials))
	rows = frappe.db.sql(
		f"""
		SELECT
			so_item.parent as order_name,
			so_item.serial_numbers
		FROM
			`tabSales Order Item` so_item
		INNER JOIN
			`tabSales Order` so ON so.name = so_item.parent
		WHERE
			({like_conditions})
			AND so.docstatus < 2
			AND so.cancelled_status = 'Uncancelled'
			AND so.name != %s
	""",
		(*[f"%{s}%" for s in serials], sales_order_name or ""),
		as_dict=True,
	)

	used = {}
	for row in rows:
		if row.order_name in related_orders:
			continue
		row_serials = {s.strip() for s in (row.serial_numbers or "").split("\n") if s.strip()}
		for serial in serials:
			if serial in row_serials and serial not in used:
				used[serial] = row.order_name
	return used


REFERENCE_FIELDS = ("haravan_ref_order_id", "is_split_order", "split_order_group")


def has_serial_relevant_changes(sales_order):
	"""
	True when this save could change the auto-fill result: a new order, a changed reference or
	split group, or an item added, removed or with its serial changed. Other saves skip the walk.
	"""
	before = sales_order.get_doc_before_save()
	if not before:
		return True

	if any(before.get(field) != sales_order.get(field) for field in REFERENCE_FIELDS):
		return True

	def serials_by_row(doc):
		return {row.name: _serial(row) for row in (doc.get("items") or [])}

	return serials_by_row(before) != serials_by_row(sales_order)


def autofill_missing_serials(sales_order):
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

	from erpnext.selling.doctype.sales_order.sales_order import _tokenize_serials

	serials_on_order = set()
	for item in sales_order.get("items") or []:
		serials_on_order |= _tokenize_serials(_serial(item)) if _serial(item) else set()

	def is_serial_free_on_order(serial):
		tokens = _tokenize_serials(serial)
		return bool(tokens) and not tokens & serials_on_order

	matches = match_missing_serials(missing_items, ref_levels, is_serial_free_on_order)
	if not matches:
		return {}

	# One duplicate check for every matched serial
	tokens = sorted({t for serial, _ref, _rule in matches.values() for t in _tokenize_serials(serial)})
	used = get_serials_used_elsewhere(
		tokens, sales_order.name, set(sales_order.get_all_related_sales_orders() or [])
	)
	matches = {
		name: match for name, match in matches.items() if not _tokenize_serials(match[0]) & used.keys()
	}

	for item in missing_items:
		if item.name in matches:
			item.db_set("serial_numbers", matches[item.name][0])

	return matches
