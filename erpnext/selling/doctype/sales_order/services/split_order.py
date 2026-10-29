# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def sync_split_order_group(sales_order):
	"""
	Ensure child split orders inherit the parent's split_order_group ID
	and synchronize Payment Entry references.
	"""
	if not (sales_order.is_split_order and sales_order.split_order_group_name):
		return

	# 1. Root / Parent Order: order_number matches split_order_group_name
	if sales_order.order_number and sales_order.order_number == sales_order.split_order_group_name:
		if not sales_order.split_order_group:
			sales_order.split_order_group = sales_order.haravan_order_id or sales_order.name
		return

	# 2. Child Order: order_number != split_order_group_name
	needs_sync = (
		(sales_order.haravan_order_id and sales_order.split_order_group == sales_order.haravan_order_id)
		or not sales_order.split_order_group
		or (hasattr(sales_order, "has_value_changed") and sales_order.has_value_changed("split_order_group_name"))
	)

	if needs_sync:
		parent = frappe.db.get_value(
			"Sales Order",
			{"order_number": sales_order.split_order_group_name},
			["name", "split_order_group", "haravan_order_id", "is_split_order"],
			as_dict=True,
		) or frappe.db.get_value(
			"Sales Order",
			{"name": sales_order.split_order_group_name},
			["name", "split_order_group", "haravan_order_id", "is_split_order"],
			as_dict=True,
		)

		if parent:
			target_group = parent.split_order_group or parent.haravan_order_id or parent.name
			if sales_order.split_order_group != target_group:
				sales_order.split_order_group = target_group

			update_fields = {}
			if not parent.split_order_group:
				update_fields["split_order_group"] = target_group
			if not parent.is_split_order:
				update_fields["is_split_order"] = 1
			if update_fields:
				frappe.db.set_value("Sales Order", parent.name, update_fields)

			if sales_order.name and not sales_order.is_new():
				frappe.db.sql(
					"""
					UPDATE `tabPayment Entry Reference`
					SET split_order_group_name = %s
					WHERE reference_doctype = 'Sales Order' AND reference_name = %s
				""",
					(sales_order.split_order_group_name, sales_order.name),
				)


@frappe.whitelist()
def link_to_split_group(sales_order_name, split_order_group_name, split_reason="Customer Request"):
	"""
	Link a Sales Order to a split order group by group name (parent order_number or name).
	Allowed for users with write permission on Sales Order.
	"""
	if not sales_order_name or not split_order_group_name:
		frappe.throw(_("Both Sales Order name and target split group name are required."))

	so = frappe.get_doc("Sales Order", sales_order_name)
	so.check_permission("write")

	so.is_split_order = 1
	so.split_order_group_name = split_order_group_name
	if split_reason and not so.split_reason:
		so.split_reason = split_reason

	so.save()
	return {
		"status": "success",
		"message": _("Sales Order {0} linked to split group {1}.").format(
			so.order_number or so.name, so.split_order_group_name
		),
		"split_order_group": so.split_order_group,
		"split_order_group_name": so.split_order_group_name,
	}


@frappe.whitelist()
def unlink_from_split_group(sales_order_name):
	"""
	Unlink a Sales Order from its split order group.
	Allowed only for Administrator or System Manager.
	"""
	if not sales_order_name:
		frappe.throw(_("Sales Order name is required."))

	so = frappe.get_doc("Sales Order", sales_order_name)

	old_group = so.split_order_group

	# Standalone values
	standalone_group = so.haravan_order_id or so.name
	standalone_group_name = so.order_number or so.name

	# 1. Reset target Sales Order to standalone
	so.db_set({
		"split_order_group": standalone_group,
		"split_order_group_name": standalone_group_name,
		"is_split_order": 0,
		"split_reason": "",
	})

	# 2. Update Payment Entry Reference for this order
	frappe.db.sql(
		"""
		UPDATE `tabPayment Entry Reference`
		SET split_order_group_name = %s
		WHERE reference_doctype = 'Sales Order' AND reference_name = %s
	""",
		(standalone_group_name, so.name),
	)

	# 3. Collapse old group if only 1 order remains
	if old_group:
		remaining = frappe.get_all(
			"Sales Order",
			filters={
				"split_order_group": old_group,
				"is_split_order": 1,
				"name": ["!=", so.name],
				"cancelled_status": "Uncancelled",
			},
			fields=["name", "order_number", "haravan_order_id"],
		)

		if len(remaining) == 1:
			last_so = remaining[0]
			last_group = last_so.haravan_order_id or last_so.name
			last_group_name = last_so.order_number or last_so.name

			frappe.db.set_value(
				"Sales Order",
				last_so.name,
				{
					"split_order_group": last_group,
					"split_order_group_name": last_group_name,
					"is_split_order": 0,
					"split_reason": "",
				},
			)
			frappe.db.sql(
				"""
				UPDATE `tabPayment Entry Reference`
				SET split_order_group_name = %s
				WHERE reference_doctype = 'Sales Order' AND reference_name = %s
			""",
				(last_group_name, last_so.name),
			)

	frappe.db.commit()
	return {
		"status": "success",
		"message": _("Sales Order {0} unlinked from split group.").format(standalone_group_name),
	}


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

	filters = {"split_order_group": split_order_group, "is_split_order": 1}

	if not include_cancelled:
		filters["cancelled_status"] = "Uncancelled"

	orders = frappe.get_all(
		"Sales Order",
		filters=filters,
		fields=[
			"name",
			"order_number",
			"customer",
			"customer_name",
			"grand_total",
			"currency",
			"haravan_order_id",
			"cancelled_status",
			"financial_status",
			"fulfillment_status",
			"transaction_date",
			"modified",
		],
		order_by="transaction_date asc",
	)
	for order in orders:
		order["is_original_order"] = order.get("haravan_order_id") == split_order_group

	return orders
