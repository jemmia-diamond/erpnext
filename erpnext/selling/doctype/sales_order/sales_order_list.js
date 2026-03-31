frappe.listview_settings["Sales Order"] = {
	hide_name_column: true,
	add_fields: [
		"base_grand_total",
		"customer_name",
		"currency",
		"delivery_date",
		"per_delivered",
		"per_billed",
		"status",
		"advance_payment_status",
		"order_type",
		"name",
		"skip_delivery_note",
	],
	get_indicator: function (doc) {
		if (doc.status === "Closed") {
			// Closed
			return [__("Closed"), "green", "status,=,Closed"];
		} else if (doc.status === "On Hold") {
			// on hold
			return [__("On Hold"), "orange", "status,=,On Hold"];
		} else if (doc.status === "Completed") {
			return [__("Completed"), "green", "status,=,Completed"];
		} else if (doc.advance_payment_status === "Requested") {
			return [__("To Pay"), "gray", "advance_payment_status,=,Requested"];
		} else if (!doc.skip_delivery_note && flt(doc.per_delivered) < 100) {
			if (frappe.datetime.get_diff(doc.delivery_date) < 0) {
				// not delivered & overdue
				return [
					__("Overdue"),
					"red",
					"per_delivered,<,100|delivery_date,<,Today|status,!=,Closed|docstatus,=,1",
				];
			} else if (flt(doc.grand_total) === 0) {
				// not delivered (zeroount order)
				return [
					__("To Deliver"),
					"orange",
					"per_delivered,<,100|grand_total,=,0|status,!=,Closed|docstatus,=,1",
				];
			} else if (flt(doc.per_billed) < 100) {
				// not delivered & not billed
				return [
					__("To Deliver and Bill"),
					"orange",
					"per_delivered,<,100|per_billed,<,100|status,!=,Closed",
				];
			} else {
				// not billed
				return [__("To Deliver"), "orange", "per_delivered,<,100|per_billed,=,100|status,!=,Closed"];
			}
		} else if (
			flt(doc.per_delivered) === 100 &&
			flt(doc.grand_total) !== 0 &&
			flt(doc.per_billed) < 100
		) {
			// to bill
			return [__("To Bill"), "orange", "per_delivered,=,100|per_billed,<,100|status,!=,Closed"];
		} else if (doc.skip_delivery_note && flt(doc.per_billed) < 100) {
			return [__("To Bill"), "orange", "per_billed,<,100|status,!=,Closed"];
		}
	},
	onload: function (listview) {
		var method = "erpnext.selling.doctype.sales_order.sales_order.close_or_unclose_sales_orders";

		listview.page.add_action_item(__("Close"), function () {
			listview.call_for_selected_items(method, { status: "Closed" });
		});

		listview.page.add_action_item(__("Re-open"), function () {
			listview.call_for_selected_items(method, { status: "Submitted" });
		});

		if (frappe.model.can_create("Sales Invoice")) {
			listview.page.add_action_item(__("Sales Invoice"), () => {
				erpnext.bulk_transaction_processing.create(listview, "Sales Order", "Sales Invoice");
			});
		}

		if (frappe.model.can_create("Delivery Note")) {
			listview.page.add_action_item(__("Delivery Note"), () => {
				frappe.call({
					method: "erpnext.selling.doctype.sales_order.sales_order.is_enable_cutoff_date_on_bulk_delivery_note_creation",
					callback: (r) => {
						if (r.message) {
							var dialog = new frappe.ui.Dialog({
								title: __("Select Items up to Delivery Date"),
								fields: [
									{
										fieldtype: "Date",
										fieldname: "delivery_date",
										default: frappe.datetime.add_days(frappe.datetime.nowdate(), 1),
									},
								],
							});
							dialog.set_primary_action(__("Select"), function (values) {
								var until_delivery_date = values.delivery_date;
								erpnext.bulk_transaction_processing.create(
									listview,
									"Sales Order",
									"Delivery Note",
									{
										until_delivery_date,
									}
								);
								dialog.hide();
							});
							dialog.show();
						} else {
							erpnext.bulk_transaction_processing.create(
								listview,
								"Sales Order",
								"Delivery Note"
							);
						}
					},
				});
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
