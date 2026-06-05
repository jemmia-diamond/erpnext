import frappe
from frappe.utils import getdate, nowdate

import json

@frappe.whitelist(methods=["GET", "POST"])
def get_tracked_sales_orders(so_names, today_str):
    if isinstance(so_names, str):
        so_names = json.loads(so_names)
    if not so_names:
        return []
    trackings = frappe.get_all(
        "Order and Debt Tracking",
        filters=[
            ["parenttype", "=", "Sales Order"],
            ["parent", "in", so_names],
            ["creation", "between", [f"{today_str} 00:00:00", f"{today_str} 23:59:59"]]
        ],
        fields=["parent"],
        ignore_permissions=True
    )
    return list({t.parent for t in trackings})

@frappe.whitelist(methods=["GET", "POST"])
def get_debt_list(from_date=None, from_the_last_check=False):
    import frappe
    from frappe.utils import getdate, nowdate
    """
    Fetch the list of debts for Sales Orders, deducting refunds from Buyback Exchange.

    Args:
        from_date (str): Expected payment date up to which to fetch (YYYY-MM-DD).
                         Defaults to today.
        from_the_last_check (bool/str): If true, filters out Sales Orders that already
                                        have an 'Order and Debt Tracking' record created today.
    """
    if not from_date:
        from_date = frappe.utils.add_days(nowdate(), 7)

    # 1. Fetch eligible Sales Orders
    filters = [
        ["balance_group_payment", ">", 1],
        ["cancelled_status", "=", "Uncancelled"],
        ["financial_status", "in", ["Pending", "Partially Paid"]],
        ["customer_name", "not like", "%test%"],
        ["customer_name", "not like", "%jemmia%"],
        ["customer_name", "not like", "%cskh%"],
        ["expected_payment_date", "is", "set"],
        ["expected_payment_date", "<=", from_date]
    ]

    fields = [
        "name",
        "split_order_group_name",
        "order_number",
        "customer",
        "customer_name",
        "real_order_date",
        "expected_payment_date",
        "balance_group_payment"
    ]

    sales_orders = frappe.get_all("Sales Order", filters=filters, fields=fields, order_by="expected_payment_date asc")

    if not sales_orders:
        return {"data": []}

    # 2. Group the Sales Orders
    group_map = {}
    for row in sales_orders:
        key = "::".join([
            row.get("split_order_group_name") or "",
            row.get("customer") or "",
            row.get("customer_name") or "",
            str(row.get("real_order_date") or ""),
            str(row.get("expected_payment_date") or ""),
            str(row.get("balance_group_payment") or 0)
        ])

        if key not in group_map:
            group_map[key] = {
                "name": row.get("name"),
                "split_order_group_name": row.get("split_order_group_name"),
                "order_number": row.get("order_number"),
                "customer": row.get("customer"),
                "customer_name": row.get("customer_name"),
                "real_order_date": row.get("real_order_date"),
                "expected_payment_date": row.get("expected_payment_date"),
                "balance_group_payment": float(row.get("balance_group_payment") or 0),
                "so_names": [row.get("name")]
            }
        else:
            if row.get("order_number"):
                if not group_map[key]["order_number"] or row.get("order_number") < group_map[key]["order_number"]:
                    group_map[key]["order_number"] = row.get("order_number")
                    group_map[key]["name"] = row.get("name")
            group_map[key]["so_names"].append(row.get("name"))

    grouped = list(group_map.values())

    # 3. Collect codes for Buyback Exchange lookup
    search_codes = set()
    for row in grouped:
        if row["split_order_group_name"]:
            search_codes.add(row["split_order_group_name"])
        else:
            if row["order_number"]:
                search_codes.add(row["order_number"])
            for n in row["so_names"]:
                if n:
                    search_codes.add(n)

    # 4. Fetch Buyback Exchanges
    buybacks = []
    if search_codes:
        buybacks = frappe.get_all("Buyback Exchange",
            filters=[
                ["new_order_code", "in", list(search_codes)],
                ["status", "!=", "CANCELED"]
            ],
            fields=["new_order_code", "refund_amount"]
        )

    # Map buybacks by code
    buyback_map = {}
    for bb in buybacks:
        code = bb.new_order_code
        if code:
            buyback_map[code] = buyback_map.get(code, 0) + (float(bb.refund_amount) or 0)

    # 5. Calculate actual debt and filter
    final_debts = []
    for row in grouped:
        buyback_sum = 0

        if row["split_order_group_name"]:
            buyback_sum += buyback_map.get(row["split_order_group_name"], 0)
        else:
            if row["order_number"]:
                buyback_sum += buyback_map.get(row["order_number"], 0)
            for n in row["so_names"]:
                buyback_sum += buyback_map.get(n, 0)

        actual_debt = float(row["balance_group_payment"]) - buyback_sum

        if actual_debt > 1:
            row["buyback_refund_amount"] = buyback_sum
            row["actual_debt"] = actual_debt
            final_debts.append(row)

    # 6. Filter by 'from_the_last_check' (exclude orders tracked today)
    # Convert from_the_last_check to actual boolean (handles "true", "1", True, etc.)
    from_the_last_check_bool = frappe.utils.cint(from_the_last_check) or str(from_the_last_check).lower() == "true"

    if from_the_last_check_bool and final_debts:
        today = nowdate()
        all_so_names = set()
        for row in final_debts:
            all_so_names.update(row["so_names"])

        if all_so_names:

            # Find tracking records created today for these sales orders
            trackings = frappe.get_all(
                "Order and Debt Tracking",
                filters=[
                    ["parenttype", "=", "Sales Order"],
                    ["parent", "in", list(all_so_names)],
                    ["creation", "between", [f"{today} 00:00:00", f"{today} 23:59:59"]]
                ],
                fields=["parent"]
            )

            tracked_sos = {t.parent for t in trackings}

            if tracked_sos:
                # Remove any group where at least one of its Sales Orders was tracked today
                filtered_final_debts = []
                for row in final_debts:
                    if not set(row["so_names"]).intersection(tracked_sos):
                        filtered_final_debts.append(row)
                final_debts = filtered_final_debts

    return { "data": final_debts }
