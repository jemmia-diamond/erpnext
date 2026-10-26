import frappe
from frappe.utils import add_to_date, flt, now_datetime


@frappe.whitelist()
def remap_payment_entries_from_cancelled_orders(hours=1, sales_orders=None):
	"""
	Hourly cron job, also callable by hand (SO form / list view button):
	Repoints Payment Entries still referencing a cancelled Sales Order to the
	active order that replaced it.

	1. Find Payment Entry References (Sales Order) whose order has cancelled_status == 'Cancelled'
	   and was modified in the last `hours` hours (hours=None scans all, e.g. for a backfill).
	   If `sales_orders` (a name or a list of names) is given, only those orders are checked
	   and the time window is ignored.
	2. Resolve the live replacement (via ref_sales_orders / haravan_ref_order_id, walking chains)
	3. Save the Payment Entry with the new reference. Payment Entry.update_sales_order_financials
	   re-saves both the old and the new order, so the old order's payment_entries clear
	   themselves and the new order picks the payment up.

	Only Payment Entries with a single Sales Order reference are handled; ones that
	reference several orders are left untouched.

	Idempotent: once remapped, the Payment Entry no longer matches step 1.
	Orders without a live replacement yet are skipped and retried on the next run.
	"""
	# frappe.has_permission("Payment Entry", "write", throw=True)

	if isinstance(sales_orders, str):
		sales_orders = frappe.parse_json(sales_orders) if sales_orders.startswith("[") else [sales_orders]

	if sales_orders:
		modified_filter = "AND so.name IN %(sales_orders)s"
		values = {"sales_orders": tuple(sales_orders)}
	elif hours:
		modified_filter = "AND so.modified >= %(since)s"
		values = {"since": add_to_date(now_datetime(), hours=-flt(hours))}
	else:
		modified_filter = ""
		values = {}

	stale_refs = frappe.db.sql(
		"""
		SELECT DISTINCT pr.parent AS payment_entry, pr.reference_name AS sales_order
		FROM `tabPayment Entry Reference` pr
		INNER JOIN `tabPayment Entry` pe ON pe.name = pr.parent
		INNER JOIN `tabSales Order` so ON so.name = pr.reference_name
		WHERE pr.parenttype = 'Payment Entry'
		  AND pr.reference_doctype = 'Sales Order'
		  AND pe.docstatus < 2
		  AND so.cancelled_status = 'Cancelled'
		  AND (
			SELECT COUNT(*) FROM `tabPayment Entry Reference` r
			WHERE r.parent = pe.name AND r.reference_doctype = 'Sales Order'
		  ) = 1
		  {modified_filter}
		""".format(modified_filter=modified_filter),
		values,
		as_dict=True,
	)

	result = {"remapped": [], "no_replacement": [], "failed": [], "messages": []}
	target_cache = {}
	for row in stale_refs:
		old_so = row.sales_order
		if old_so not in target_cache:
			target_cache[old_so] = find_active_replacement(old_so)

		target = target_cache[old_so]
		if not target:
			result["no_replacement"].append({"payment_entry": row.payment_entry, "from": old_so})
			continue

		try:
			remap_payment_entry(row.payment_entry, old_so, target)
			frappe.db.commit()
			result["remapped"].append({"payment_entry": row.payment_entry, "from": old_so, "to": target})
		except Exception as e:
			frappe.db.rollback()
			result["failed"].append({"payment_entry": row.payment_entry, "from": old_so, "to": target})
			frappe.log_error(
				f"Error remapping Payment Entry {row.payment_entry} from {old_so} to {target}: {e!s}",
				"Payment Entry Remap Error",
			)

	result["messages"] = build_messages(result, sales_orders)
	return result


def order_label(sales_order):
	"""What sales sees: the order number, falling back to the system name."""
	return frappe.db.get_value("Sales Order", sales_order, "order_number") or sales_order


def order_label(sales_order):
	"""What sales sees: the order number, falling back to the system name."""
	return frappe.db.get_value("Sales Order", sales_order, "order_number") or sales_order


def build_messages(result, sales_orders):
	"""Plain Vietnamese sentences for sales users, one line per reason."""
	messages = []

	moved = {}
	for r in result["remapped"]:
		moved.setdefault((r["from"], r["to"]), []).append(r["payment_entry"])
	for (old_so, new_so), pes in moved.items():
		messages.append(
			f"Đã chuyển thanh toán {', '.join(pes)} từ đơn {order_label(old_so)} sang đơn {order_label(new_so)}."
		)

	no_replacement = _unique(r["from"] for r in result["no_replacement"])
	if no_replacement:
		messages.append(
			f"Đơn {_join_orders(no_replacement)} đã hủy nhưng chưa tìm thấy đơn mới để chuyển thanh toán. "
			"Đơn mới phải cùng khách hàng, được tạo sau đơn cũ, chưa bị hủy và có giá trị lớn hơn 0."
		)

	failed = _unique(r["from"] for r in result["failed"])
	if failed:
		messages.append(
			f"Không chuyển được thanh toán của đơn {_join_orders(failed)}. Vui lòng báo bộ phận IT."
		)

	handled = {r["from"] for key in ("remapped", "no_replacement", "failed") for r in result[key]}
	reasons = {}
	for so in _unique(sales_orders or []):
		if so not in handled:
			reason, label = explain_no_match(so)
			reasons.setdefault(reason, []).append(label)
	for reason, labels in reasons.items():
		messages.append(reason.format(orders=", ".join(labels)))

	return messages or ["Không có gì để chuyển."]


def explain_no_match(sales_order):
	"""Returns (reason template with an {orders} placeholder, order label)."""
	status = frappe.db.get_value("Sales Order", sales_order, "cancelled_status")
	if status is None:
		return "Không tìm thấy đơn {orders}.", sales_order

	label = order_label(sales_order)
	if status != "Cancelled":
		return "Đơn {orders} chưa bị hủy nên không cần chuyển thanh toán.", label

	has_payment = frappe.db.sql(
		"""
		SELECT 1
		FROM `tabPayment Entry Reference` pr
		INNER JOIN `tabPayment Entry` pe ON pe.name = pr.parent
		WHERE pr.parenttype = 'Payment Entry'
		  AND pr.reference_doctype = 'Sales Order'
		  AND pr.reference_name = %s
		  AND pe.docstatus < 2
		LIMIT 1
		""",
		sales_order,
	)
	if not has_payment:
		return "Đơn {orders} không còn khoản thanh toán nào cần chuyển (có thể đã được chuyển rồi).", label
	return (
		"Thanh toán của đơn {orders} dùng cho nhiều đơn cùng lúc nên hệ thống không tự chuyển. "
		"Vui lòng báo bộ phận IT.",
		label,
	)


def _unique(items):
	return list(dict.fromkeys(items))


def _join_orders(sales_orders):
	return ", ".join(order_label(so) for so in sales_orders)


def find_active_replacement(cancelled_so):
	"""
	Resolves the live order that took over a cancelled Sales Order's payments.

	Candidates are found by walking forward from the cancelled order (SO1 -> SO2 -> SO3)
	via ref_sales_orders / haravan_ref_order_id, then widened with their uncancelled split
	siblings. A candidate is valid only if it is uncancelled, has the same customer, a
	financial_status of Pending / Partially Paid / Paid, grand_total > 0, and was created
	after the cancelled order. The closest one in time wins, which for a split group is also the
	first split order (see is_first_split_order).
	"""
	cancelled = frappe.db.get_value("Sales Order", cancelled_so, ["customer", "creation"], as_dict=True)

	visited = {cancelled_so}
	to_visit = [cancelled_so]
	active = set()

	while to_visit:
		current = to_visit.pop()
		current_haravan_id = frappe.db.get_value("Sales Order", current, "haravan_order_id")

		successors = set(
			frappe.db.get_all(
				"Sales Order Reference",
				filters={"sales_order": current, "parenttype": "Sales Order"},
				pluck="parent",
			)
		)
		if current_haravan_id:
			successors.update(
				frappe.db.get_all(
					"Sales Order", filters={"haravan_ref_order_id": current_haravan_id}, pluck="name"
				)
			)

		for name in successors - visited:
			visited.add(name)
			status = frappe.db.get_value("Sales Order", name, "cancelled_status")
			if status == "Cancelled":
				to_visit.append(name)
			else:
				active.add(name)

	if not active:
		return None

	# A linked order may be one of several split orders; the group's first order owns the payment
	split_groups = {
		g
		for g in frappe.db.get_all(
			"Sales Order", filters={"name": ["in", list(active)], "is_split_order": 1}, pluck="split_order_group"
		)
		if g
	}
	if split_groups:
		active.update(
			frappe.db.get_all(
				"Sales Order",
				filters={
					"split_order_group": ["in", list(split_groups)],
					"is_split_order": 1,
					"cancelled_status": "Uncancelled",
				},
				pluck="name",
			)
		)

	candidates = frappe.db.get_all(
		"Sales Order",
		filters={
			"name": ["in", list(active)],
			"cancelled_status": "Uncancelled",
			"customer": cancelled.customer,
			"financial_status": ["in", ["Pending", "Partially Paid", "Paid"]],
			"grand_total": [">", 0],
			"creation": [">", cancelled.creation],
		},
		order_by="creation asc",
		limit=1,
		pluck="name",
	)
	return candidates[0] if candidates else None


def remap_payment_entry(payment_entry, old_so, new_so):
	new_order = frappe.db.get_value(
		"Sales Order", new_so, ["order_number", "split_order_group_name"], as_dict=True
	)

	pe = frappe.get_doc("Payment Entry", payment_entry)
	changed = False
	for ref in pe.references:
		if ref.reference_doctype == "Sales Order" and ref.reference_name == old_so:
			ref.reference_name = new_so
			ref.order_number = new_order.order_number
			ref.split_order_group_name = new_order.split_order_group_name
			changed = True

	if changed:
		pe.flags.ignore_validate_update_after_submit = True
		pe.save(ignore_permissions=True)
