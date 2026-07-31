frappe.listview_settings["Opportunity"] = {
	hide_name_column: true,
	hide_liked_by: true,
	get_indicator: function (doc) {
		const colors = {
			"Proposal": "blue",
			"Negotiation": "orange",
			"Nurturing": "purple",
			"Delayed": "cyan",
			"Won": "green",
			"Lost": "red"
		};
		const color = colors[doc.status] || "gray";
		return [__(doc.status), color, "status,=," + doc.status];
	},
	onload: function (listview) {
		// var method = "erpnext.crm.doctype.opportunity.opportunity.set_multiple_status";

		// listview.page.add_menu_item(__("Set as Open"), function () {
		// 	listview.call_for_selected_items(method, { status: "Open" });
		// });

		// listview.page.add_menu_item(__("Set as Closed"), function () {
		// 	listview.call_for_selected_items(method, { status: "Closed" });
		// });

		if (listview.page.fields_dict.opportunity_from) {
			listview.page.fields_dict.opportunity_from.get_query = function () {
				return {
					filters: {
						name: ["in", ["Customer", "Lead"]],
					},
				};
			};
		}
	},
};
