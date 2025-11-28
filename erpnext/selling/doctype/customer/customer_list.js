frappe.listview_settings["Customer"] = {
	onload: function(listview) {
		listview.page.add_actions_menu_item(__("Re-evaluate Rank"), function() {
			let selected = listview.get_checked_items();

			if (selected.length === 0) {
				frappe.msgprint(__("Please select at least one customer"));
				return;
			}

			if (selected.length > 500) {
				frappe.msgprint({
					message: __("You can only re-evaluate up to 500 customers at a time. You selected {0}.", [selected.length]),
					title: __("Too Many Customers"),
					indicator: "red"
				});
				return;
			}

			frappe.confirm(
				__("Re-evaluate rank for {0} selected customer(s)?", [selected.length]),
				function() {
					frappe.call({
						method: "erpnext.selling.doctype.customer.customer.bulk_reevaluate_customer_rank",
						args: {
							customer_names: selected.map(item => item.name)
						},
						freeze: true,
						freeze_message: __("Re-evaluating {0} customers...", [selected.length]),
						callback: function(r) {
							if (r.message) {
								frappe.msgprint({
									message: __("Successfully re-evaluated"),
									title: __("Rank Re-evaluation Complete"),
									indicator: "green"
								});
								listview.refresh();
							}
						}
					});
				}
			);
		});
	},
	add_fields: ["customer_name", "rank", "territory", "customer_group", "customer_type", "image"],
};
