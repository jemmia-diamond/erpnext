frappe.listview_settings["Sales Order"] = {
	hide_name_column: true,
	onload: function (listview) {
		var method = "erpnext.selling.doctype.sales_order.sales_order.close_or_unclose_sales_orders";

		listview.page.add_menu_item(__("Close"), function () {
			listview.call_for_selected_items(method, { status: "Closed" });
		});

		listview.page.add_menu_item(__("Re-open"), function () {
			listview.call_for_selected_items(method, { status: "Submitted" });
		});

		if (frappe.model.can_create("Sales Invoice")) {
			listview.page.add_action_item(__("Sales Invoice"), () => {
				erpnext.bulk_transaction_processing.create(listview, "Sales Order", "Sales Invoice");
			});
		}

		if (frappe.model.can_create("Delivery Note")) {
			listview.page.add_action_item(__("Delivery Note"), () => {
				erpnext.bulk_transaction_processing.create(listview, "Sales Order", "Delivery Note");
			});
		}

		if (frappe.model.can_create("Payment Entry")) {
			listview.page.add_action_item(__("Advance Payment"), () => {
				erpnext.bulk_transaction_processing.create(listview, "Sales Order", "Payment Entry");
			});
		}
	},

	refresh: function (listview) {
		// Hide the 3rd column (docstatus) in the list view using jQuery
		$("<style>.result .list-header-subject > div:nth-child(3), .result .list-row-container .list-row-col:nth-child(3) { display: none; }</style>").appendTo("head");
		// Hide comments and heart count columns
		$("<style>.result .level .level-right { display: none; }</style>").appendTo("head");

		// Add MutationObserver to .result for DOM changes
		const resultEl = document.querySelector('.result');
		if (resultEl) {
			const observer = new MutationObserver(function (mutationsList, observer) {
				// Order Number
				for (let i = 0; i < listview.data.length; i++) {
					if (listview.data[i].cancelled_status === "Uncancelled") {
						$(`.result .list-row-container:nth-child(${i + 3}) .list-row-col:nth-child(1) a`).css("color", "rgb(35, 98, 235)");
					} else {
						$(`.result .list-row-container:nth-child(${i + 3}) .list-row-col:nth-child(1) a`).css("color", "rgb(219, 48, 48)");
					}
				}

				$('span[data-filter]').removeAttr('class').addClass('indicator-pill').addClass('no-indicator-dot').addClass('filterable');
				// Cancelled Status
				$('span[data-filter="cancelled_status,=,Uncancelled"]').addClass('green');
				$('span[data-filter="cancelled_status,=,Cancelled"]').addClass('red');
				// Fulfillment Status
				$('span[data-filter="fulfillment_status,=,Fulfilled"]').addClass('green');
				$('span[data-filter="fulfillment_status,=,Not Fulfilled"]').addClass('yellow');
				// Financial Status
				$('span[data-filter="financial_status,=,Paid"]').addClass('green');
				$('span[data-filter="financial_status,=,Partially Paid"]').addClass('gray');
				$('span[data-filter="financial_status,=,Pending"]').addClass('blue');
				
				// Split Order Indicator - Add badge to order number
				for (let i = 0; i < listview.data.length; i++) {
					const row_data = listview.data[i];
					if (row_data.is_split_order && row_data.split_order_group) {
						const badge = `<span style="background: #3498db; color: white; padding: 2px 6px; border-radius: 3px; font-size: 9px; margin-left: 5px; font-weight: bold;">SPLIT</span>`;
						$(`.result .list-row-container:nth-child(${i + 3}) .list-row-col:nth-child(1)`).append(badge);
					}
				}
			});
			observer.observe(resultEl, { childList: true, subtree: true });
		}
		// Remove the title status
		$(".page-head-content .title-area span").removeAttr('style').text("");
	}
};
