# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from erpnext.selling.doctype.sales_order.services.serial_autofill import (
	RULE_TEMPORARY_TO_REAL,
	RULE_VARIANT,
	get_reference_chain_levels,
	is_temporary_to_real_match,
	match_missing_serials,
)

RING_SKU = "JRIFC2305481D18WWN115"


def item(name, sku, serial="", vid=None, price=28360000, product_type="Nhẫn Nữ", parent=None):
	return frappe._dict(
		name=name,
		parent=parent,
		sku=sku,
		serial_numbers=serial,
		haravan_variant_id=vid,
		price_list_rate=price,
		rate=price,
		type=product_type,
		item_name=name,
	)


def allow_all(serial):
	return True


class TestTemporaryToRealMatch(UnitTestCase):
	def test_same_price_and_type_matches(self):
		self.assertTrue(
			is_temporary_to_real_match(item("ring", RING_SKU), item("spt", "SPT-2498", "26100101"))
		)

	def test_type_compare_ignores_case_and_spaces(self):
		ref = item("spt", "SPT-2498", "26100101", product_type=" nhẫn nữ ")
		self.assertTrue(is_temporary_to_real_match(item("ring", RING_SKU), ref))

	def test_price_falls_back_to_rate(self):
		cur = item("ring", RING_SKU)
		cur.price_list_rate = 0
		self.assertTrue(is_temporary_to_real_match(cur, item("spt", "SPT-2498", "26100101")))

	def test_different_price_does_not_match(self):
		ref = item("spt", "SPT-2348", "26090075", price=21970100)
		self.assertFalse(is_temporary_to_real_match(item("ring", RING_SKU, price=21970000), ref))

	def test_different_type_does_not_match(self):
		ref = item("spt", "SPT-2412", "26090175", product_type="Nhẫn Nữ")
		self.assertFalse(
			is_temporary_to_real_match(item("ring", RING_SKU, product_type="Nhẫn Nữ Nguyên Chiếc"), ref)
		)

	def test_ref_must_be_temporary_and_current_must_not(self):
		self.assertFalse(is_temporary_to_real_match(item("ring", RING_SKU), item("ref", RING_SKU, "1")))
		self.assertFalse(is_temporary_to_real_match(item("spt-cur", "SPT-1"), item("spt", "SPT-2", "1")))

	def test_missing_price_or_type_does_not_match(self):
		self.assertFalse(
			is_temporary_to_real_match(item("ring", RING_SKU, price=0), item("spt", "SPT-1", "1", price=0))
		)
		self.assertFalse(
			is_temporary_to_real_match(
				item("ring", RING_SKU, product_type=""), item("spt", "SPT-1", "1", product_type="")
			)
		)


class TestMatchMissingSerials(UnitTestCase):
	def test_spt_found_deep_in_chain(self):
		# #ORDER118286: level 2 has the ring without serial, level 3 has SPT-2498 with 26100101
		ring = item("ring", RING_SKU, vid="1176408960")
		levels = [
			[item("gift", "QT00000000080")],
			[item("ring-l2", RING_SKU, vid="1176408960")],
			[item("spt", "SPT-2498", "26100101", vid="1176173352")],
		]
		self.assertEqual(match_missing_serials([ring], levels, allow_all)["ring"][0], "26100101")
		self.assertEqual(match_missing_serials([ring], levels, allow_all)["ring"][2], RULE_TEMPORARY_TO_REAL)

	def test_variant_beats_spt_even_when_deeper(self):
		ring = item("ring", RING_SKU, vid="1")
		levels = [[item("spt", "SPT-1", "111")], [item("old", RING_SKU, "222", vid="1")]]
		match = match_missing_serials([ring], levels, allow_all)["ring"]
		self.assertEqual((match[0], match[2]), ("222", RULE_VARIANT))

	def test_nearest_level_wins(self):
		ring = item("ring", RING_SKU, vid="1")
		levels = [[item("l1", RING_SKU, "111", vid="1")], [item("l2", RING_SKU, "222", vid="1")]]
		self.assertEqual(match_missing_serials([ring], levels, allow_all)["ring"][0], "111")

	def test_two_different_serials_on_same_level_is_ambiguous(self):
		ring = item("ring", RING_SKU)
		levels = [[item("spt1", "SPT-1", "111"), item("spt2", "SPT-2", "222")]]
		self.assertEqual(match_missing_serials([ring], levels, allow_all), {})

	def test_serial_claimed_by_two_items_is_skipped(self):
		ring_a = item("a", RING_SKU)
		ring_b = item("b", RING_SKU)
		levels = [[item("spt", "SPT-1", "111")]]
		self.assertEqual(match_missing_serials([ring_a, ring_b], levels, allow_all), {})

	def test_disallowed_serial_is_not_used(self):
		ring = item("ring", RING_SKU)
		levels = [[item("spt", "SPT-1", "111")]]
		self.assertEqual(match_missing_serials([ring], levels, lambda s: False), {})

	def test_price_mismatch_is_not_filled(self):
		ring = item("ring", RING_SKU, price=39895000, product_type="Bông Tai")
		levels = [[item("spt", "SPT-2322", "26080162", price=33485000, product_type="Bông Tai")]]
		self.assertEqual(match_missing_serials([ring], levels, allow_all), {})


class TestReferenceChainLevels(UnitTestCase):
	def test_walks_levels_and_stops_on_cycles(self):
		# SO-0 -> SO-1 -> SO-2 -> SO-1 (cycle)
		refs = {"SO-1": ["SO-2"], "SO-2": ["SO-1", "SO-0"]}
		so = frappe._dict(name="SO-0", get_candidate_reference_orders=lambda: ["SO-1"])

		def get_all(doctype, filters=None, fields=None, **kwargs):
			return [frappe._dict(name=n) for n in filters["name"][1]]

		with (
			patch("frappe.db.get_all", side_effect=get_all),
			patch(
				"erpnext.selling.doctype.sales_order.services.serial_autofill.get_candidate_reference_orders",
				side_effect=lambda order: refs.get(order.name, []),
			),
		):
			self.assertEqual(get_reference_chain_levels(so), [["SO-1"], ["SO-2"]])

	def test_respects_max_depth(self):
		so = frappe._dict(name="SO-0", get_candidate_reference_orders=lambda: ["SO-1"])

		def get_all(doctype, filters=None, fields=None, **kwargs):
			return [frappe._dict(name=n) for n in filters["name"][1]]

		with (
			patch("frappe.db.get_all", side_effect=get_all),
			patch(
				"erpnext.selling.doctype.sales_order.services.serial_autofill.get_candidate_reference_orders",
				side_effect=lambda order: [f"SO-{int(order.name.split('-')[1]) + 1}"],
			),
		):
			self.assertEqual(len(get_reference_chain_levels(so, max_depth=3)), 3)
