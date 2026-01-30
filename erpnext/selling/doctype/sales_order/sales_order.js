// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

cur_frm.cscript.tax_table = "Sales Taxes and Charges";

erpnext.accounts.taxes.setup_tax_filters("Sales Taxes and Charges");
erpnext.accounts.taxes.setup_tax_validations("Sales Order");
erpnext.sales_common.setup_selling_controller();

frappe.ui.form.on("Sales Order", {
	setup: function (frm) {
		frm.custom_make_buttons = {
			"Delivery Note": "Delivery Note",
			"Pick List": "Pick List",
			"Sales Invoice": "Sales Invoice",
			"Material Request": "Material Request",
			"Purchase Order": "Purchase Order",
			"Project": "Project",
			"Payment Entry": "Payment",
			"Work Order": "Work Order",
		};
		frm.add_fetch("customer", "tax_id", "tax_id");

		// formatter for material request item
		frm.set_indicator_formatter("item_code", function (doc) {
			return doc.stock_qty <= doc.delivered_qty ? "green" : "orange";
		});

		frm.set_query("bom_no", "items", function (doc, cdt, cdn) {
			var row = locals[cdt][cdn];
			return {
				filters: {
					item: row.item_code,
				},
			};
		});

		frm.set_df_property("packed_items", "cannot_add_rows", true);
		frm.set_df_property("packed_items", "cannot_delete_rows", true);
	},

	refresh: function (frm) {
		// Disable Submit button
		$(".primary-action").prop("disabled", true);
		// Indicate cancelled status
		const $statusSpan = $(".page-head-content .title-area span");
		$statusSpan.text(__(frm.doc.cancelled_status));
		// Set color based on cancelled_status value
		if (frm.doc.cancelled_status === "Uncancelled") {
			$statusSpan.css("color", "green").css("background-color", "whitesmoke");
		} else if (frm.doc.cancelled_status === "Cancelled") {
			$statusSpan.css("color", "tomato").css("background-color", "whitesmoke");
		}

		// Show split order indicator and add button to view related orders
		if (frm.doc.is_split_order && frm.doc.split_order_group) {
			// Format split_order_group for display (add # prefix for readability)
			const formatted_group = `#${frm.doc.split_order_group}`;

			// Check if this is the original order (group origin)
			const is_original = frm.doc.haravan_order_id === frm.doc.split_order_group;

			// Add indicator
			if (is_original) {
				frm.dashboard.add_indicator(
					__('Split Order Group: {0} (Original Order)', [formatted_group]),
					'orange'
				);
			} else {
				frm.dashboard.add_indicator(
					__('Split Order Group: {0}', [formatted_group]),
					'blue'
				);
			}

			// Add button to view related split orders
			frm.add_custom_button(__('View Related Split Orders'), function() {
				frappe.route_options = {
					"split_order_group": frm.doc.split_order_group,
					"is_split_order": 1,
					"cancelled_status": "Uncancelled"
				};
				frappe.set_route("List", "Sales Order");
			}, __("Actions"));

			// Load and display related split orders in the form
			frappe.call({
				method: 'frappe.client.get_list',
				args: {
					doctype: 'Sales Order',
					filters: {
						'split_order_group': frm.doc.split_order_group,
						'is_split_order': 1,
						'cancelled_status': 'Uncancelled'
					},
					fields: ['name', 'order_number', 'grand_total', 'haravan_order_id'],
					order_by: 'transaction_date asc',
					limit_page_length: 20
				},
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						// Calculate total of all orders in group
						let total_group_amount = 0;
						let all_orders = r.message;

						all_orders.forEach(function(order) {
							total_group_amount += order.grand_total || 0;
						});

						let html = '<div class="split-orders-info" style="margin-top: 10px; padding: 10px; background-color: #f0f4f7; border-radius: 5px;">';
						html += `<h6 style="margin-bottom: 10px; color: #3498db; font-size: 13px;"><i class="fa fa-link"></i> All Orders in Split Group: <b>${all_orders.length}</b></h6>`;
						html += '<ul style="margin: 0; padding-left: 20px;">';

						all_orders.forEach(function(order) {
							const is_original = order.haravan_order_id === frm.doc.split_order_group;
							const is_current = order.name === frm.doc.name;

							let badge = '';
							if (is_original) {
								badge = '<span style="background: #95a5a6; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; margin-left: 5px;">ORIGINAL</span>';
							}

							const style = is_current ? 'font-weight: bold;' : '';
							html += `<li style="${style}"><a href="/app/sales-order/${order.name}" target="_blank">${order.order_number}</a> - ${format_currency(order.grand_total, frm.doc.currency)}${badge}</li>`;
						});

						html += '</ul>';
						html += '<div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #d1d8dd;">';
						html += `<p style="margin: 5px 0; font-size: 13px; color: #2c3e50;"><b>Total Amount (All Split Orders): ${format_currency(total_group_amount, frm.doc.currency)}</b></p>`;
						html += '</div>';
						html += '</div>';

						frm.set_df_property('split_order_group', 'description', html);
					}
				}
			});
		}

		frm.add_custom_button(__('View On Haravan'), function() {
			const haravanUrl = `https://jemmiavn.myharavan.com/admin/orders/${frm.doc.haravan_order_id}`;
			window.open(haravanUrl, '_blank');
		});

		frm.add_custom_button(__("Send Order To Lark"), frappe.utils.debounce(() => {
			frappe.db.get_doc("Sales Order", frm.doc.name).then((doc) => {

				const btn = frm.custom_buttons[__("Send Order To Lark")];
				$(btn).prop("disabled", true);

				let attachments = frm.attachments.get_attachments();
				attachments = attachments.map(att => {
					const file_url = frm.attachments.get_file_url(att);
					return {
						file_url: frappe.urllib.get_full_url(decodeURIComponent(file_url)), // Decode first to avoid double encoding
						is_private: att.is_private
					}
				})

				const docWithAttachments = {
					...doc,
					attachments: attachments
				}

				frappe.call({
					method: "erpnext.selling.doctype.sales_order.sales_order.larksuite_notification",
					args: { sales_order_doc: docWithAttachments },
					callback: (r) => {
						if (r.message) frappe.msgprint(r.message);
					},
					always: () => {
						$(btn).prop("disabled", false);
					}
				});
			});
		}, 2000));

		// hide sales order item grid footer (buttons)
		$('[data-fieldname="items"] .grid-footer').addClass('hidden');

		// fetch customer details
		frappe.db.get_doc("Customer", frm.doc.customer).then((doc) => {
			frm.set_value("birth_date", doc.birth_date);
			frm.set_value("place_of_issuance", doc.place_of_issuance);
			frm.set_value("date_of_issuance", doc.date_of_issuance);
			frm.set_value("customer_personal_id", doc.personal_id);
			frm.set_value("customer_passport_id", doc.passport_id);
			frm.set_value("gender", doc.gender);
		})

		// link filters for promotions
		frm.set_query("promotions", function () {
            return {
                filters: {
                    "scope": "Order",
					"is_active": 1
                }
            };
        });

		if (frm.doc.docstatus === 1) {
			if (
				frm.doc.status !== "Closed" &&
				flt(frm.doc.per_delivered) < 100 &&
				flt(frm.doc.per_billed) < 100 &&
				frm.has_perm("write")
			) {
				frm.add_custom_button(__("Update Items"), () => {
					erpnext.utils.update_child_items({
						frm: frm,
						child_docname: "items",
						child_doctype: "Sales Order Detail",
						cannot_add_row: false,
						has_reserved_stock: frm.doc.__onload && frm.doc.__onload.has_reserved_stock,
					});
				});

				// Stock Reservation > Reserve button should only be visible if the SO has unreserved stock and no Pick List is created against the SO.
				if (
					frm.doc.__onload &&
					frm.doc.__onload.has_unreserved_stock &&
					flt(frm.doc.per_picked) === 0
				) {
					frm.add_custom_button(
						__("Reserve"),
						() => frm.events.create_stock_reservation_entries(frm),
						__("Stock Reservation")
					);
				}
			}

			// Stock Reservation > Unreserve button will be only visible if the SO has un-delivered reserved stock.
			if (
				frm.doc.__onload &&
				frm.doc.__onload.has_reserved_stock &&
				frappe.model.can_cancel("Stock Reservation Entry")
			) {
				frm.add_custom_button(
					__("Unreserve"),
					() => frm.events.cancel_stock_reservation_entries(frm),
					__("Stock Reservation")
				);
			}

			frm.doc.items.forEach((item) => {
				if (flt(item.stock_reserved_qty) > 0 && frappe.model.can_read("Stock Reservation Entry")) {
					frm.add_custom_button(
						__("Reserved Stock"),
						() => frm.events.show_reserved_stock(frm),
						__("Stock Reservation")
					);
					return;
				}
			});
		}

		if (frm.doc.docstatus === 0) {
			if (frm.doc.is_internal_customer) {
				frm.events.get_items_from_internal_purchase_order(frm);
			}

			if (frm.doc.docstatus === 0) {
				frappe.call({
					method: "erpnext.selling.doctype.sales_order.sales_order.get_stock_reservation_status",
					callback: function (r) {
						if (!r.message) {
							frm.set_value("reserve_stock", 0);
							frm.set_df_property("reserve_stock", "read_only", 1);
							frm.set_df_property("reserve_stock", "hidden", 1);
							frm.fields_dict.items.grid.update_docfield_property("reserve_stock", "hidden", 1);
							frm.fields_dict.items.grid.update_docfield_property(
								"reserve_stock",
								"default",
								0
							);
							frm.fields_dict.items.grid.update_docfield_property(
								"reserve_stock",
								"read_only",
								1
							);
						}
					},
				});
			}
		}

		// Hide `Reserve Stock` field description in submitted or cancelled Sales Order.
		if (frm.doc.docstatus > 0) {
			frm.set_df_property("reserve_stock", "description", null);
		}

		// Ensure deposit_amount shows currency in label and formats using SO currency
		if (frm.doc.currency) {
			frm.set_currency_labels(["deposit_amount"], frm.doc.order_currency);
			frm.set_df_property("deposit_amount", "options", "currency");
		}

		// Handle buyback button visibility and click
		const can_add_buyback = !frm.doc.__islocal && frm.doc.docstatus === 0;
		frm.toggle_display('buyback_items', can_add_buyback);
		
		if (can_add_buyback) {
			// For Button field, bind to the input element
			frm.fields_dict.buyback_items.$input.off('click').on('click', function() {
				frm.trigger('show_buyback_selector');
			});
		}

		frm.trigger('render_buyback_items');
	},
	
	show_buyback_selector(frm) {
		// Get customer phone from sales order
		const phone = frm.doc.contact_mobile || frm.doc.contact_phone;

		if (!phone) {
			frappe.msgprint(__('Please set customer phone before selecting buyback items.'));
			return;
		}
		
		// Fetch available buyback items
		frappe.call({
			method: 'erpnext.selling.doctype.sales_order.sales_order.get_available_buyback_items',
			args: {
				phone: phone
			},
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					frm.events.open_buyback_dialog(frm, r.message);
				} else {
					frappe.msgprint(__('No available buyback items found for this customer phone.'));
				}
			}
		});
	},

	open_buyback_dialog(frm, items) {
		let d = new frappe.ui.Dialog({
			title: __('Select Buyback Items to Link'),
			size: 'large',
			fields: [
				{
					fieldname: 'items_html',
					fieldtype: 'HTML'
				}
			],
			primary_action_label: __('Link Selected Items'),
			primary_action(values) {
				const selected = [];
				d.$wrapper.find('input[type="checkbox"]:checked').each(function() {
					selected.push($(this).data('item-name'));
				});
				
				if (selected.length === 0) {
					frappe.msgprint(__('Please select at least one item'));
					return;
				}
				
				frappe.call({
					method: 'erpnext.selling.doctype.sales_order.sales_order.link_buyback_items',
					args: {
						sales_order: frm.doc.name,
						item_names: selected
					},
					callback: function(r) {
						if (r.message && r.message.success) {
							frappe.show_alert({
								message: __('Successfully linked {0} buyback item(s)', [r.message.count]),
								indicator: 'green'
							});
							d.hide();
							frm.trigger('render_buyback_items');
						}
					}
				});
			}
		});

		// Build HTML table with direct borders (simple)
		let html = `
			<div style="margin-top: 8px;">
				<div style="max-height: 450px; overflow-y: auto; overflow-x: auto;">
					<table class="table table-bordered" style="margin-bottom: 0; border-collapse: collapse; width: 100%; min-width: 800px; table-layout: fixed;">
						<thead>
							<tr style="background: linear-gradient(180deg, #f8f9fb 0%, #f3f4f6 100%); border-bottom: 2px solid #e4e7eb;">
								<th style="padding: 14px 16px; width: 5%; border-bottom: none; text-align: center;">
									<!-- No Select All for single selection -->
								</th>
								<th style="padding: 14px 16px; font-weight: 600; font-size: 12px; color: #4b5563; letter-spacing: 0.5px; border-bottom: none; width: 20%; text-align: center;">${__("Product")}</th>
								<th style="padding: 14px 16px; font-weight: 600; font-size: 12px; color: #4b5563; letter-spacing: 0.5px; border-bottom: none; width: 16%; text-align: center;">${__("Item Code")}</th>
								<th style="padding: 14px 16px; font-weight: 600; font-size: 12px; color: #4b5563; letter-spacing: 0.5px; border-bottom: none; width: 16%; text-align: center;">${__("Sale Price")}</th>
								<th style="padding: 14px 16px; font-weight: 600; font-size: 12px; color: #4b5563; letter-spacing: 0.5px; border-bottom: none; width: 16%; text-align: center;">${__("Buyback Price")}</th>
								<th style="padding: 14px 16px; font-weight: 600; font-size: 12px; color: #4b5563; letter-spacing: 0.5px; border-bottom: none; width: 16%; text-align: center;">${__("Buyback %")}</th>
								<th style="padding: 14px 16px; font-weight: 600; font-size: 12px; color: #4b5563; letter-spacing: 0.5px; border-bottom: none; width: 16%; text-align: center;">${__("Prev Sales Order")}</th>
							</tr>
						</thead>
						<tbody>
		`;

		// Escape text to HTML entities to be safe in JS strings and HTML
		const escape = (str) => (str || "").toString()
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;")
			.replace(/'/g, "&#39;");

		// Normalize frappe.format output: verify no single quotes break the template
		const safeFormat = (val, doc) => {
			let s = frappe.format(val, {fieldtype: 'Currency', currency: doc.currency});
			// Replace single quotes in HTML attributes with double quotes to be template-safe
			return (s || "").toString().replace(/'/g, '"');
		};

		items.forEach((item, index) => {
			const prevOrder = item.prev_sales_order || item.order_code;
			const rowBg = index % 2 === 0 ? '#ffffff' : '#fafbfc';
			html += `
				<tr style="background-color: ${rowBg}; border-bottom: 1px solid #f0f1f3; transition: background-color 0.15s ease;">
					<td style="padding: 16px; vertical-align: middle; text-align: center; border-bottom: 1px solid #f0f1f3;">
						<input type="checkbox" class="buyback-item-checkbox" data-item-name="${escape(item.name)}" style="width: 16px; height: 16px; cursor: pointer;">
					</td>
					<td style="padding: 16px; vertical-align: middle; border-bottom: 1px solid #f0f1f3;">
						<div style="font-size: 14px; color: #111827; line-height: 1.4; word-wrap: break-word;" title="${escape(item.product_name)}">${escape(item.product_name || "-")}</div>
					</td>
					<td style="padding: 16px; vertical-align: middle; border-bottom: 1px solid #f0f1f3;">
						<div style="font-size: 12px; color: #374151; line-height: 1.6;">
							<span style="font-family: Menlo, Monaco, Consolas, monospace; color: #111827;">${escape(item.item_code)}</span>
						</div>
					</td>
					<td style="padding: 16px; vertical-align: middle; text-align: right; border-bottom: 1px solid #f0f1f3; color: #111827;">
						${safeFormat(item.sale_price, frm.doc)}
					</td>
					<td style="padding: 16px; vertical-align: middle; text-align: right; border-bottom: 1px solid #f0f1f3; color: #111827;">
						${safeFormat(item.buyback_price, frm.doc)}
					</td>
					<td style="padding: 16px; vertical-align: middle; text-align: center; border-bottom: 1px solid #f0f1f3; color: #111827;">
						${item.buyback_percentage}%
					</td>
					<td style="padding: 16px; vertical-align: middle; text-align: center; border-bottom: 1px solid #f0f1f3;">
						${prevOrder ? `<a href="/app/sales-order/${escape(prevOrder)}" target="_blank" style="text-decoration: underline;">${escape(prevOrder)}</a>` : "-"}
					</td>
				</tr>
			`;
		});

		html += `
						</tbody>
					</table>
				</div>
			</div>
		`;

		d.fields_dict.items_html.$wrapper.html(html);

		// Single selection logic: uncheck others when one is checked
		d.$wrapper.find('.buyback-item-checkbox').on('change', function() {
			if ($(this).prop('checked')) {
				d.$wrapper.find('.buyback-item-checkbox').not(this).prop('checked', false);
			}
		});

		d.show();
	},

	render_buyback_items(frm) {
		if (frm.doc.__islocal) return;
		frappe.call({
			method: "erpnext.selling.doctype.sales_order.sales_order.get_buyback_items",
			args: {
				sales_order: frm.doc.name
			},
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					let html = `
						<div class="control-value" style="margin-top: 8px;">
							<div style="max-height: 450px; overflow-y: auto; overflow-x: auto;">
								<table class="table table-bordered" style="margin-bottom: 0; border-collapse: collapse; width: 100%; min-width: 800px; table-layout: fixed;">
									<thead>
										<tr style="background: linear-gradient(180deg, #f8f9fb 0%, #f3f4f6 100%); border-bottom: 2px solid #e4e7eb;">
											<th style="padding: 14px 16px; font-weight: 600; font-size: 12px; color: #4b5563; letter-spacing: 0.5px; border-bottom: none; width: 20%; text-align: center;">${__("Product")}</th>
											<th style="padding: 14px 16px; font-weight: 600; font-size: 12px; color: #4b5563; letter-spacing: 0.5px; border-bottom: none; width: 17%; text-align: center;">${__("Item Code")}</th>
											<th style="padding: 14px 16px; font-weight: 600; font-size: 12px; color: #4b5563; letter-spacing: 0.5px; text-align: center; border-bottom: none; width: 15%;">${__("Sale Price")}</th>
											<th style="padding: 14px 16px; font-weight: 600; font-size: 12px; color: #4b5563; letter-spacing: 0.5px; text-align: center; border-bottom: none; width: 15%;">${__("Exchange Amount")}</th>
											<th style="padding: 14px 16px; font-weight: 600; font-size: 12px; color: #4b5563; letter-spacing: 0.5px; border-bottom: none; text-align: center; width: 12%;">${__("Buyback %")}</th>
											<th style="padding: 14px 16px; font-weight: 600; font-size: 12px; color: #4b5563; letter-spacing: 0.5px; text-align: center; border-bottom: none; width: 16%;">${__("Prev Sales Order")}</th>
											<th style="padding: 14px 16px; width: 9%; border-bottom: none; text-align: center;">${__("Actions")}</th>
										</tr>
									</thead>
									<tbody>
					`;
					
					// Escape text to HTML entities
					const escape = (str) => (str || "").toString()
						.replace(/&/g, "&amp;")
						.replace(/</g, "&lt;")
						.replace(/>/g, "&gt;")
						.replace(/"/g, "&quot;")
						.replace(/'/g, "&#39;");

					// Normalize frappe.format output
					const safeFormat = (val, doc) => {
						let s = frappe.format(val, {fieldtype: 'Currency', currency: doc.currency});
						return (s || "").toString().replace(/'/g, '"');
					};

					r.message.forEach((item, index) => {
						const prevOrder = item.prev_sales_order || item.order_code;
						const rowBg = index % 2 === 0 ? '#ffffff' : '#fafbfc';
						html += `
							<tr style="background-color: ${rowBg}; border-bottom: 1px solid #f0f1f3; transition: background-color 0.15s ease;">
								<td style="padding: 16px; vertical-align: middle; border-bottom: 1px solid #f0f1f3;">
									<div style="font-size: 14px; color: #111827; margin-bottom: 4px; line-height: 1.4; word-wrap: break-word;" title="${escape(item.product_name)}">${escape(item.product_name || "-")}</div>
								</td>
								<td style="padding: 16px; vertical-align: middle; border-bottom: 1px solid #f0f1f3;">
									<div style="font-size: 12px; color: #374151; line-height: 1.6;">
										<span style="font-family: Menlo, Monaco, Consolas, monospace; color: #111827;">${escape(item.item_code)}</span>
									</div>
								</td>
								<td style="padding: 16px; vertical-align: middle; text-align: right; border-bottom: 1px solid #f0f1f3; color: #111827;">
									${safeFormat(item.sale_price, frm.doc)}
								</td>
								<td style="padding: 16px; vertical-align: middle; text-align: right; border-bottom: 1px solid #f0f1f3; color: #111827;">
									${safeFormat(item.buyback_price, frm.doc)}
								</td>
								<td style="padding: 16px; vertical-align: middle; text-align: center; border-bottom: 1px solid #f0f1f3; color: #111827;">
									${item.buyback_percentage}%
								</td>
								<td style="padding: 16px; vertical-align: middle; text-align: center; border-bottom: 1px solid #f0f1f3;">
									${prevOrder ? `<a href="/app/sales-order/${escape(prevOrder)}" target="_blank" style="text-decoration: underline;">${escape(prevOrder)}</a>` : "-"}
								</td>
								<td style="padding: 16px; vertical-align: middle; text-align: center; border-bottom: 1px solid #f0f1f3;">
									<div style="display: flex; justify-content: center; gap: 8px;">
										<a href="/app/buyback-exchange/${escape(item.parent)}" class="btn btn-sm" title="${__('View Exchange')}" target="_blank" style="padding: 6px 10px; background-color: #f3f4f6; border: 1px solid #d1d5db; border-radius: 6px; color: #374151; transition: all 0.15s ease;">
											<i class="fa fa-external-link" style="font-size: 12px;"></i>
										</a>
										<button class="btn btn-sm btn-unlink-buyback" data-item-name="${escape(item.name)}" title="${__('Unlink Item')}" style="padding: 6px 10px; background-color: #fee2e2; border: 1px solid #fca5a5; border-radius: 6px; color: #dc2626; transition: all 0.15s ease;">
											<i class="fa fa-times" style="font-size: 12px;"></i>
										</button>
									</div>
								</td>
							</tr>
						`;
					});
					
					html += `
									</tbody>
								</table>
							</div>
						</div>
					`;
					
					frm.set_df_property("buyback_items_html", "options", html);
					frm.set_df_property("buyback_items_html", "hidden", 0);
					frm.set_df_property("buyback_section_break", "hidden", 0);
					
					// Add click handlers for unlink buttons
					setTimeout(() => {
						if (frm.fields_dict.buyback_items_html && frm.fields_dict.buyback_items_html.$wrapper) {
							frm.fields_dict.buyback_items_html.$wrapper.find('.btn-unlink-buyback').off('click').on('click', function(e) {
								e.preventDefault();
								const item_name = $(this).data('item-name');
								
								frappe.confirm(
									__('Are you sure you want to unlink this buyback item?'),
									() => {
										frappe.call({
											method: 'erpnext.selling.doctype.sales_order.sales_order.unlink_buyback_item',
											args: { item_name: item_name },
											callback: function(r) {
												if (r.message && r.message.success) {
													frappe.show_alert({
														message: __('Buyback item unlinked successfully'),
														indicator: 'green'
													});
													frm.trigger('render_buyback_items');
												}
											}
										});
									}
								);
							});
						}
					}, 100);
				} else {
					// Hide only the items table, not the section
					frm.set_df_property("buyback_items_html", "hidden", 1);
				}
				
				// Always show the Buyback section
				frm.set_df_property("buyback_section_break", "hidden", 0);
			}
		});
	},

	get_items_from_internal_purchase_order(frm) {
		if (!frappe.model.can_read("Purchase Order")) {
			return;
		}

		frm.add_custom_button(
			__("Purchase Order"),
			() => {
				erpnext.utils.map_current_doc({
					method: "erpnext.buying.doctype.purchase_order.purchase_order.make_inter_company_sales_order",
					source_doctype: "Purchase Order",
					target: frm,
					setters: [
						{
							label: __("Supplier"),
							fieldname: "supplier",
							fieldtype: "Link",
							options: "Supplier",
						},
					],
					get_query_filters: {
						company: frm.doc.company,
						is_internal_supplier: 1,
						docstatus: 1,
						status: ["!=", "Completed"],
					},
				});
			},
			__("Get Items From")
		);
	},

	onload: function (frm) {
		if (!frm.doc.transaction_date) {
			frm.set_value("transaction_date", frappe.datetime.get_today());
		}
		erpnext.queries.setup_queries(frm, "Warehouse", function () {
			return {
				filters: [["Warehouse", "company", "in", ["", cstr(frm.doc.company)]]],
			};
		});

		frm.set_query("warehouse", "items", function (doc, cdt, cdn) {
			let row = locals[cdt][cdn];
			let query = {
				filters: [["Warehouse", "company", "in", ["", cstr(frm.doc.company)]]],
			};
			if (row.item_code) {
				query.query = "erpnext.controllers.queries.warehouse_query";
				query.filters.push(["Bin", "item_code", "=", row.item_code]);
			}
			return query;
		});

		// On cancel and amending a sales order with advance payment, reset advance paid amount
		if (frm.is_new()) {
			frm.set_value("advance_paid", 0);
		}

		frm.ignore_doctypes_on_cancel_all = [
			"Purchase Order",
			"Unreconcile Payment",
			"Unreconcile Payment Entries",
		];
	},

	// Update deposit_amount label and currency formatting when currency changes
	currency: function (frm) {
		if (frm.doc.currency) {
			frm.set_currency_labels(["deposit_amount"], frm.doc.order_currency);
			frm.set_df_property("deposit_amount", "options", "currency");
		}
	},

	birth_date: function (frm) {
		if (frm.doc.birth_date) {
			const year = parseInt(frm.doc.birth_date.split("-")[0]);
			const current_year = new Date().getFullYear();

			if (year < 1900 || year > current_year) {
				frappe.msgprint(__("Năm sinh phải nằm trong khoảng 1900 đến {0}", [current_year]));
				frm.set_value("birth_date", "");
			}
		}
	},

	delivery_date: function (frm) {
		$.each(frm.doc.items || [], function (i, d) {
			if (!d.delivery_date) d.delivery_date = frm.doc.delivery_date;
		});
		refresh_field("items");
	},

	create_stock_reservation_entries(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __("Stock Reservation"),
			size: "extra-large",
			fields: [
				{
					fieldname: "set_warehouse",
					fieldtype: "Link",
					label: __("Set Warehouse"),
					options: "Warehouse",
					default: frm.doc.set_warehouse,
					get_query: () => {
						return {
							filters: [["Warehouse", "is_group", "!=", 1]],
						};
					},
					onchange: () => {
						if (dialog.get_value("set_warehouse")) {
							dialog.fields_dict.items.df.data.forEach((row) => {
								row.warehouse = dialog.get_value("set_warehouse");
							});
							dialog.fields_dict.items.grid.refresh();
						}
					},
				},
				{ fieldtype: "Column Break" },
				{
					fieldname: "add_item",
					fieldtype: "Link",
					label: __("Add Item"),
					options: "Sales Order Item",
					get_query: () => {
						return {
							query: "erpnext.controllers.queries.get_filtered_child_rows",
							filters: {
								parenttype: frm.doc.doctype,
								parent: frm.doc.name,
								reserve_stock: 1,
							},
						};
					},
					onchange: () => {
						let sales_order_item = dialog.get_value("add_item");

						if (sales_order_item) {
							frm.doc.items.forEach((item) => {
								if (item.name === sales_order_item) {
									let unreserved_qty =
										(flt(item.stock_qty) -
											(item.stock_reserved_qty
												? flt(item.stock_reserved_qty)
												: flt(item.delivered_qty) * flt(item.conversion_factor))) /
										flt(item.conversion_factor);

									if (unreserved_qty > 0) {
										dialog.fields_dict.items.df.data.forEach((row) => {
											if (row.sales_order_item === sales_order_item) {
												unreserved_qty -= row.qty_to_reserve;
											}
										});
									}

									dialog.fields_dict.items.df.data.push({
										sales_order_item: item.name,
										item_code: item.item_code,
										warehouse: dialog.get_value("set_warehouse") || item.warehouse,
										qty_to_reserve: Math.max(unreserved_qty, 0),
									});
									dialog.fields_dict.items.grid.refresh();
									dialog.set_value("add_item", undefined);
								}
							});
						}
					},
				},
				{ fieldtype: "Section Break" },
				{
					fieldname: "items",
					fieldtype: "Table",
					label: __("Items to Reserve"),
					allow_bulk_edit: false,
					cannot_add_rows: true,
					cannot_delete_rows: true,
					data: [],
					fields: [
						{
							fieldname: "sales_order_item",
							fieldtype: "Link",
							label: __("Sales Order Item"),
							options: "Sales Order Item",
							reqd: 1,
							in_list_view: 1,
							get_query: () => {
								return {
									query: "erpnext.controllers.queries.get_filtered_child_rows",
									filters: {
										parenttype: frm.doc.doctype,
										parent: frm.doc.name,
										reserve_stock: 1,
									},
								};
							},
							onchange: (event) => {
								if (event) {
									let name = $(event.currentTarget).closest(".grid-row").attr("data-name");
									let item_row =
										dialog.fields_dict.items.grid.grid_rows_by_docname[name].doc;

									frm.doc.items.forEach((item) => {
										if (item.name === item_row.sales_order_item) {
											item_row.item_code = item.item_code;
										}
									});
									dialog.fields_dict.items.grid.refresh();
								}
							},
						},
						{
							fieldname: "item_code",
							fieldtype: "Link",
							label: __("Item Code"),
							options: "Item",
							reqd: 1,
							read_only: 1,
							in_list_view: 1,
						},
						{
							fieldname: "warehouse",
							fieldtype: "Link",
							label: __("Warehouse"),
							options: "Warehouse",
							reqd: 1,
							in_list_view: 1,
							get_query: () => {
								return {
									filters: [["Warehouse", "is_group", "!=", 1]],
								};
							},
						},
						{
							fieldname: "qty_to_reserve",
							fieldtype: "Float",
							label: __("Qty"),
							reqd: 1,
							in_list_view: 1,
						},
					],
				},
			],
			primary_action_label: __("Reserve Stock"),
			primary_action: () => {
				var data = { items: dialog.fields_dict.items.grid.get_selected_children() };

				if (data.items && data.items.length > 0) {
					frappe.call({
						doc: frm.doc,
						method: "create_stock_reservation_entries",
						args: {
							items_details: data.items,
							notify: true,
						},
						freeze: true,
						freeze_message: __("Reserving Stock..."),
						callback: (r) => {
							frm.doc.__onload.has_unreserved_stock = false;
							frm.reload_doc();
						},
					});

					dialog.hide();
				} else {
					frappe.msgprint(__("Please select items to reserve."));
				}
			},
		});

		frm.doc.items.forEach((item) => {
			if (item.reserve_stock) {
				let unreserved_qty =
					(flt(item.stock_qty) -
						(item.stock_reserved_qty
							? flt(item.stock_reserved_qty)
							: flt(item.delivered_qty) * flt(item.conversion_factor))) /
					flt(item.conversion_factor);

				if (unreserved_qty > 0) {
					dialog.fields_dict.items.df.data.push({
						__checked: 1,
						sales_order_item: item.name,
						item_code: item.item_code,
						warehouse: item.warehouse,
						qty_to_reserve: unreserved_qty,
					});
				}
			}
		});

		dialog.fields_dict.items.grid.refresh();
		dialog.show();
	},

	cancel_stock_reservation_entries(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __("Stock Unreservation"),
		 size: "extra-large",
			fields: [
				{
					fieldname: "sr_entries",
					fieldtype: "Table",
					label: __("Reserved Stock"),
					allow_bulk_edit: false,
					cannot_add_rows: true,
					cannot_delete_rows: true,
					in_place_edit: true,
					data: [],
					fields: [
						{
							fieldname: "sre",
							fieldtype: "Link",
							label: __("Stock Reservation Entry"),
							options: "Stock Reservation Entry",
							reqd: 1,
							read_only: 1,
							in_list_view: 1,
						},
						{
							fieldname: "item_code",
							fieldtype: "Link",
							label: __("Item Code"),
							options: "Item",
							reqd: 1,
							read_only: 1,
							in_list_view: 1,
						},
						{
							fieldname: "warehouse",
							fieldtype: "Link",
							label: __("Warehouse"),
							options: "Warehouse",
							reqd: 1,
							read_only: 1,
							in_list_view: 1,
						},
						{
							fieldname: "qty",
							fieldtype: "Float",
							label: __("Qty"),
							reqd: 1,
							read_only: 1,
							in_list_view: 1,
						},
					],
				},
			],
			primary_action_label: __("Unreserve Stock"),
			primary_action: () => {
				var data = { sr_entries: dialog.fields_dict.sr_entries.grid.get_selected_children() };

				if (data.sr_entries && data.sr_entries.length > 0) {
					frappe.call({
						doc: frm.doc,
						method: "cancel_stock_reservation_entries",
						args: {
							sre_list: data.sr_entries.map((item) => item.sre),
						},
						freeze: true,
						freeze_message: __("Unreserving Stock..."),
						callback: (r) => {
							frm.doc.__onload.has_reserved_stock = false;
							frm.reload_doc();
						},
					});

					dialog.hide();
				} else {
					frappe.msgprint(__("Please select items to unreserve."));
				}
			},
		});

		frappe
			.call({
				method: "erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry.get_stock_reservation_entries_for_voucher",
				args: {
					voucher_type: frm.doctype,
					voucher_no: frm.docname,
				},
				callback: (r) => {
					if (!r.exc && r.message) {
						r.message.forEach((sre) => {
							if (flt(sre.reserved_qty) > flt(sre.delivered_qty)) {
								dialog.fields_dict.sr_entries.df.data.push({
									sre: sre.name,
									item_code: sre.item_code,
									warehouse: sre.warehouse,
									qty: flt(sre.reserved_qty) - flt(sre.delivered_qty),
								});
							}
						});
					}
				},
			})
			.then((r) => {
				dialog.fields_dict.sr_entries.grid.refresh();
				dialog.show();
			});
	},

	show_reserved_stock(frm) {
		// Get the latest modified date from the items table.
		var to_date = moment(new Date(Math.max(...frm.doc.items.map((e) => new Date(e.modified))))).format(
			"YYYY-MM-DD"
		);

		frappe.route_options = {
			company: frm.doc.company,
			from_date: frm.doc.transaction_date,
			to_date: to_date,
			voucher_type: frm.doc.doctype,
			voucher_no: frm.doc.name,
		};
		frappe.set_route("query-report", "Reserved Stock");
	},
});

frappe.ui.form.on("Sales Order Item", {
	item_code: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (frm.doc.delivery_date) {
			row.delivery_date = frm.doc.delivery_date;
			refresh_field("delivery_date", cdn, "items");
		} else {
			frm.script_manager.copy_from_first_row("items", row, ["delivery_date"]);
		}
	},
	delivery_date: function (frm, cdt, cdn) {
		if (!frm.doc.delivery_date) {
			erpnext.utils.copy_value_in_all_rows(frm.doc, cdt, cdn, "items", "delivery_date");
		}
	},

	fetch_policy: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		frappe.call({
			method: "erpnext.selling.doctype.sales_order_item.sales_order_item.trigger_manual_webhook",
			args: { item_name: row.name },
			callback: function(r) {
				if (r.message) {
					frappe.show_alert(__('Đang tự động lấy thông tin chính sách ...'), 5);
				}
			}
		});
	},

	serial: function (frm, cdt, cdn) {
		// When serial is selected, append serial number to serial_numbers field
		var row = locals[cdt][cdn];
		if (row.serial) {
			frappe.db.get_value('Serial', row.serial, 'serial_number')
				.then((r) => {
					if (r && r.message && r.message.serial_number) {
						const serialTitle = r.message.serial_number;
						const serialNumbersList = row.serial_numbers ? row.serial_numbers.split('\n') : [];

						if (!serialNumbersList.includes(serialTitle)) {
							if (row.serial_numbers) {
								row.serial_numbers += `\n${serialTitle}`;
							} else {
								row.serial_numbers = serialTitle;
							}
						}

						// Clean up and finalize
						row.serial_numbers = row.serial_numbers.replace(/\n+/g, '\n').trim();
						row.serial = null;
						frm.refresh_field('items');
					}
				})
				.catch((err) => {
					frappe.msgprint(__('Error fetching serial number: {0}', [err.message]));
					console.error(err);
				});
		}
	},

	promotion: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (row.promotion) {
			var selected_promotions = [row.promotion_1, row.promotion_2, row.promotion_3, row.promotion_4, row.promotion_5];
			var is_earring = false;
			
			const type = row.type ? decode_unicode(row.type) : "";
			const title = row.variant_title ? decode_unicode(row.variant_title) : "";

			if (type.includes("Bông Tai") || (type.toLowerCase() === "virtual" && title.includes("Bông Tai"))) {
				is_earring = true;
			}
			
			var promotion_count = selected_promotions.filter(p => p === row.promotion).length;
			
			if (!selected_promotions.includes(row.promotion) || (is_earring && promotion_count < 2)) {

				if (!row.promotion_1) {
					row.promotion_1 = row.promotion;
				} else if (!row.promotion_2) {
					row.promotion_2 = row.promotion;
				} else if (!row.promotion_3) {
					row.promotion_3 = row.promotion;
				} else if (!row.promotion_4) {
					row.promotion_4 = row.promotion;
				} else if (!row.promotion_5) {
					row.promotion_5 = row.promotion;
				}
			}
			row.promotion = null;
			frm.refresh_field('items');
		}
	}
});

erpnext.selling.SalesOrderController = class SalesOrderController extends erpnext.selling.SellingController {
	onload(doc, dt, dn) {
		super.onload(doc, dt, dn);
	}

	refresh(doc, dt, dn) {
		var me = this;
		super.refresh();
		let allow_delivery = false;

		if (doc.docstatus == 1) {
			if (this.frm.has_perm("submit")) {
				if (doc.status === "On Hold") {
					// un-hold
					this.frm.add_custom_button(
						__("Resume"),
						function () {
							me.frm.cscript.update_status("Resume", "Draft");
						},
						__("Status")
					);

					if (flt(doc.per_delivered) < 100 || flt(doc.per_billed) < 100) {
						// close
						this.frm.add_custom_button(__("Close"), () => this.close_sales_order(), __("Status"));
					}
				} else if (doc.status === "Closed") {
					// un-close
					this.frm.add_custom_button(
						__("Re-open"),
						function () {
							me.frm.cscript.update_status("Re-open", "Draft");
						},
						__("Status")
					);
				}
			}
			if (doc.status !== "Closed") {
				if (doc.status !== "On Hold") {
					allow_delivery =
						this.frm.doc.items.some(
							(item) => item.delivered_by_supplier === 0 && item.qty > flt(item.delivered_qty)
						) && !this.frm.doc.skip_delivery_note;

					if (this.frm.has_perm("submit")) {
						if (flt(doc.per_delivered) < 100 || flt(doc.per_billed) < 100) {
							// hold
							this.frm.add_custom_button(
								__("Hold"),
								() => this.hold_sales_order(),
								__("Status")
							);
							// close
							this.frm.add_custom_button(
								__("Close"),
								() => this.close_sales_order(),
								__("Status")
							);
						}
					}

					if (
						(!doc.__onload || !doc.__onload.has_reserved_stock) &&
						flt(doc.per_picked) < 100 &&
						flt(doc.per_delivered) < 100 &&
						frappe.model.can_create("Pick List")
					) {
						this.frm.add_custom_button(
							__("Pick List"),
							() => this.create_pick_list(),
							__("Create")
						);
					}

					const order_is_a_sale = ["Sales", "Shopping Cart"].indexOf(doc.order_type) !== -1;
					const order_is_maintenance = ["Maintenance"].indexOf(doc.order_type) !== -1;
					// order type has been customised then show all the action buttons
					const order_is_a_custom_sale =
						["Sales", "Shopping Cart", "Maintenance"].indexOf(doc.order_type) === -1;

					// delivery note
					if (
						flt(doc.per_delivered) < 100 &&
						(order_is_a_sale || order_is_a_custom_sale) &&
						allow_delivery
					) {
						if (frappe.model.can_create("Delivery Note")) {
							this.frm.add_custom_button(
								__("Delivery Note"),
								() => this.make_delivery_note_based_on_delivery_date(true),
								__("Create")
							);
						}

						if (frappe.model.can_create("Work Order")) {
							this.frm.add_custom_button(
								__("Work Order"),
								() => this.make_work_order(),
								__("Create")
							);
						}
					}

					// sales invoice
					if (flt(doc.per_billed) < 100 && frappe.model.can_create("Sales Invoice")) {
						this.frm.add_custom_button(
							__("Sales Invoice"),
							() => me.make_sales_invoice(),
							__("Create")
						);
					}

					// material request
					if (
						(!doc.order_type ||
							((order_is_a_sale || order_is_a_custom_sale) && flt(doc.per_delivered) < 100)) &&
						frappe.model.can_create("Material Request")
					) {
						this.frm.add_custom_button(
							__("Material Request"),
							() => this.make_material_request(),
							__("Create")
						);
						this.frm.add_custom_button(
							__("Request for Raw Materials"),
							() => this.make_raw_material_request(),
							__("Create")
						);
					}

					// Make Purchase Order
					if (!this.frm.doc.is_internal_customer && frappe.model.can_create("Purchase Order")) {
						this.frm.add_custom_button(
							__("Purchase Order"),
							() => this.make_purchase_order(),
							__("Create")
						);
					}

					// maintenance
					if (flt(doc.per_delivered) < 100 && (order_is_maintenance || order_is_a_custom_sale)) {
						if (frappe.model.can_create("Maintenance Visit")) {
							this.frm.add_custom_button(
								__("Maintenance Visit"),
								() => this.make_maintenance_visit(),
								__("Create")
							);
						}
						if (frappe.model.can_create("Maintenance Schedule")) {
							this.frm.add_custom_button(
								__("Maintenance Schedule"),
								() => this.make_maintenance_schedule(),
								__("Create")
							);
						}
					}

					// project
					if (flt(doc.per_delivered) < 100 && frappe.model.can_create("Project")) {
						this.frm.add_custom_button(__("Project"), () => this.make_project(), __("Create"));
					}

					if (
						doc.docstatus === 1 &&
						!doc.inter_company_order_reference &&
						frappe.model.can_create("Purchase Order")
					) {
						let me = this;
						let internal = me.frm.doc.is_internal_customer;
						if (internal) {
							let button_label =
								me.frm.doc.company === me.frm.doc.represents_company
									? "Internal Purchase Order"
									: "Inter Company Purchase Order";

							me.frm.add_custom_button(
								button_label,
								function () {
									me.make_inter_company_order();
								},
								__("Create")
							);
						}
					}
				}
				// payment request
				if (flt(doc.per_billed) < 100 + frappe.boot.sysdefaults.over_billing_allowance) {
					this.frm.add_custom_button(
						__("Payment Request"),
						() => this.make_payment_request(),
						__("Create")
					);

					if (frappe.model.can_create("Payment Entry")) {
						this.frm.add_custom_button(
							__("Payment"),
							() => this.make_payment_entry(),
							__("Create")
						);
					}
				}
				this.frm.page.set_inner_btn_group_as_primary(__("Create"));
			}
		}

		this.order_type(doc);
	}

	create_pick_list() {
		frappe.model.open_mapped_doc({
			method: "erpnext.selling.doctype.sales_order.sales_order.create_pick_list",
			frm: this.frm,
		});
	}

	make_work_order() {
		var me = this;
		me.frm.call({
			method: "erpnext.selling.doctype.sales_order.sales_order.get_work_order_items",
			args: {
				sales_order: this.frm.docname,
			},
			freeze: true,
			callback: function (r) {
				if (!r.message) {
					frappe.msgprint({
						title: __("Work Order not created"),
						message: __("No Items with Bill of Materials to Manufacture"),
						indicator: "orange",
					});
					return;
				} else {
					const fields = [
						{
							label: __("Items"),
							fieldtype: "Table",
							fieldname: "items",
							description: __("Select BOM and Qty for Production"),
							fields: [
								{
									fieldtype: "Read Only",
									fieldname: "item_code",
									label: __("Item Code"),
									in_list_view: 1,
								},
								{
									fieldtype: "Link",
									fieldname: "bom",
									options: "BOM",
									reqd: 1,
									label: __("Select BOM"),
									in_list_view: 1,
									get_query: function (doc) {
										return { filters: { item: doc.item_code } };
									},
								},
								{
									fieldtype: "Float",
									fieldname: "pending_qty",
									reqd: 1,
									label: __("Qty"),
									in_list_view: 1,
								},
								{
									fieldtype: "Data",
									fieldname: "sales_order_item",
									reqd: 1,
									label: __("Sales Order Item"),
									hidden: 1,
								},
							],
							data: r.message,
							get_data: () => {
								return r.message;
							},
						},
					];
					var d = new frappe.ui.Dialog({
						title: __("Select Items to Manufacture"),
						fields: fields,
						primary_action: function () {
							var data = { items: d.fields_dict.items.grid.get_selected_children() };
							if (!data) {
								frappe.throw(__("Please select items"));
							}
							me.frm.call({
								method: "make_work_orders",
								args: {
									items: data,
									company: me.frm.doc.company,
									sales_order: me.frm.docname,
									project: me.frm.project,
								},
								freeze: true,
								callback: function (r) {
									if (r.message) {
										frappe.msgprint({
											message: __("Work Orders Created: {0}", [
												r.message
													.map(function (d) {
														return repl(
															'<a href="/app/work-order/%(name)s">%(name)s</a>',
															{ name: d }
														);
													})
													.join(", "),
											]),
											indicator: "green",
										});
									}
									d.hide();
								},
							});
						},
						primary_action_label: __("Create"),
					});
					d.show();
				}
			},
		});
	}

	order_type() {
		this.toggle_delivery_date();
	}

	tc_name() {
		this.get_terms();
	}

	make_material_request() {
		frappe.model.open_mapped_doc({
			method: "erpnext.selling.doctype.sales_order.sales_order.make_material_request",
			frm: this.frm,
		});
	}

	skip_delivery_note() {
		this.toggle_delivery_date();
	}

	toggle_delivery_date() {
		this.frm.fields_dict.items.grid.toggle_reqd(
			"delivery_date",
			this.frm.doc.order_type == "Sales" && !this.frm.doc.skip_delivery_note
		);
	}

	make_raw_material_request() {
		var me = this;
		this.frm.call({
			method: "erpnext.selling.doctype.sales_order.sales_order.get_work_order_items",
			args: {
				sales_order: this.frm.docname,
				for_raw_material_request: 1,
			},
			callback: function (r) {
				if (!r.message) {
					frappe.msgprint({
						message: __("No Items with Bill of Materials."),
						indicator: "orange",
					});
					return;
				} else {
					me.make_raw_material_request_dialog(r);
				}
			},
		});
	}

	make_raw_material_request_dialog(r) {
		var me = this;
		var fields = [
			{ fieldtype: "Check", fieldname: "include_exploded_items", label: __("Include Exploded Items") },
			{
				fieldtype: "Check",
				fieldname: "ignore_existing_ordered_qty",
				label: __("Ignore Existing Ordered Qty"),
			},
			{
				fieldtype: "Table",
				fieldname: "items",
				description: __("Select BOM, Qty and For Warehouse"),
				fields: [
					{
						fieldtype: "Read Only",
						fieldname: "item_code",
						label: __("Item Code"),
						in_list_view: 1,
					},
					{
						fieldtype: "Link",
						fieldname: "warehouse",
						options: "Warehouse",
						label: __("For Warehouse"),
						in_list_view: 1,
					},
					{
						fieldtype: "Link",
						fieldname: "bom",
						options: "BOM",
						reqd: 1,
						label: __("BOM"),
						in_list_view: 1,
						get_query: function (doc) {
							return { filters: { item: doc.item_code } };
						},
					},
					{
						fieldtype: "Float",
						fieldname: "required_qty",
						reqd: 1,
						label: __("Qty"),
					 in_list_view: 1,
					},
				],
				data: r.message,
				get_data: function () {
					return r.message;
				},
			},
		];
		var d = new frappe.ui.Dialog({
			title: __("Items for Raw Material Request"),
			fields: fields,
			primary_action: function () {
				var data = d.get_values();
				me.frm.call({
					method: "erpnext.selling.doctype.sales_order.sales_order.make_raw_material_request",
					args: {
						items: data,
						company: me.frm.doc.company,
						sales_order: me.frm.docname,
						project: me.frm.project,
					},
					freeze: true,
					callback: function (r) {
						if (r.message) {
							frappe.msgprint(
								__("Material Request {0} submitted.", [
									'<a href="/app/material-request/' +
									r.message.name +
									'">' +
									r.message.name +
									"</a>",
								])
							);
						}
						d.hide();
						me.frm.reload_doc();
					},
				});
			},
			primary_action_label: __("Create"),
		});
		d.show();
	}

	make_delivery_note_based_on_delivery_date(for_reserved_stock = false) {
		var me = this;

		var delivery_dates = this.frm.doc.items.map((i) => i.delivery_date);
		delivery_dates = [...new Set(delivery_dates)];

		var item_grid = this.frm.fields_dict["items"].grid;
		if (!item_grid.get_selected().length && delivery_dates.length > 1) {
			var dialog = new frappe.ui.Dialog({
				title: __("Select Items based on Delivery Date"),
				fields: [{ fieldtype: "HTML", fieldname: "dates_html" }],
			});

			var html = $(`
				<div style="border: 1px solid #d1d8dd">
					<div class="list-item list-item--head">
						<div class="list-item__content list-item__content--flex-2">
							${__("Delivery Date")}
						</div>
					</div>
					${delivery_dates
					.map(
						(date) => `
						<div class="list-item">
							<div class="list-item__content list-item__content--flex-2">
								<label>
								<input type="checkbox" data-date="${date}" checked="checked"/>
								${frappe.datetime.str_to_user(date)}
								</label>
							</div>
						</div>
					`
					)
					.join("")}
				</div>
			`);

			var wrapper = dialog.fields_dict.dates_html.$wrapper;
			wrapper.html(html);

			dialog.set_primary_action(__("Select"), function () {
				var dates = wrapper
					.find("input[type=checkbox]:checked")
					.map((i, el) => $(el).attr("data-date"))
					.toArray();

				if (!dates) return;

				me.make_delivery_note(dates, for_reserved_stock);
				dialog.hide();
			});
			dialog.show();
		} else {
			this.make_delivery_note([], for_reserved_stock);
		}
	}

	make_delivery_note(delivery_dates, for_reserved_stock = false) {
		frappe.model.open_mapped_doc({
			method: "erpnext.selling.doctype.sales_order.sales_order.make_delivery_note",
			frm: this.frm,
			args: {
				delivery_dates,
				for_reserved_stock: for_reserved_stock,
			},
			freeze: true,
			freeze_message: __("Creating Delivery Note ..."),
		});
	}

	make_sales_invoice() {
		frappe.model.open_mapped_doc({
			method: "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice",
			frm: this.frm,
		});
	}

	make_maintenance_schedule() {
		frappe.model.open_mapped_doc({
			method: "erpnext.selling.doctype.sales_order.sales_order.make_maintenance_schedule",
			frm: this.frm,
		});
	}

	make_project() {
		frappe.model.open_mapped_doc({
			method: "erpnext.selling.doctype.sales_order.sales_order.make_project",
			frm: this.frm,
		});
	}

	make_inter_company_order() {
		frappe.model.open_mapped_doc({
			method: "erpnext.selling.doctype.sales_order.sales_order.make_inter_company_purchase_order",
			frm: this.frm,
		});
	}

	make_maintenance_visit() {
		frappe.model.open_mapped_doc({
			method: "erpnext.selling.doctype.sales_order.sales_order.make_maintenance_visit",
			frm: this.frm,
		});
	}

	make_purchase_order() {
		let pending_items = this.frm.doc.items.some((item) => {
			let pending_qty = flt(item.stock_qty) - flt(item.ordered_qty);
			return pending_qty > 0;
		});
		if (!pending_items) {
			frappe.throw({
				message: __("Purchase Order already created for all Sales Order items"),
				title: __("Note"),
			});
		}

		var me = this;
		var dialog = new frappe.ui.Dialog({
			title: __("Select Items"),
			size: "large",
			fields: [
				{
					fieldtype: "Check",
					label: __("Against Default Supplier"),
					fieldname: "against_default_supplier",
					default: 0,
				},
				{
					fieldname: "items_for_po",
					fieldtype: "Table",
					label: __("Select Items"),
					fields: [
						{
							fieldtype: "Data",
							fieldname: "item_code",
							label: __("Item"),
							read_only: 1,
							in_list_view: 1,
						},
						{
							fieldtype: "Data",
							fieldname: "item_name",
							label: __("Item name"),
							read_only: 1,
							in_list_view: 1,
						},
						{
							fieldtype: "Float",
							fieldname: "pending_qty",
							label: __("Pending Qty"),
							read_only: 1,
							in_list_view: 1,
						},
						{
							fieldtype: "Link",
							read_only: 1,
							fieldname: "uom",
							label: __("UOM"),
							in_list_view: 1,
						},
						{
							fieldtype: "Data",
							fieldname: "supplier",
							label: __("Supplier"),
							read_only: 1,
							in_list_view: 1,
						},
					],
				},
			],
			primary_action_label: __("Create Purchase Order"),
			primary_action(args) {
				if (!args) return;

				let selected_items = dialog.fields_dict.items_for_po.grid.get_selected_children();
				if (selected_items.length == 0) {
					frappe.throw({
						message: "Please select Items from the Table",
						title: __("Items Required"),
						indicator: "blue",
					});
				}

				dialog.hide();

				var method = args.against_default_supplier
					? "make_purchase_order_for_default_supplier"
					: "make_purchase_order";
				return frappe.call({
					method: "erpnext.selling.doctype.sales_order.sales_order." + method,
					freeze_message: __("Creating Purchase Order ..."),
					args: {
						source_name: me.frm.doc.name,
						selected_items: selected_items,
					},
					freeze: true,
					callback: function (r) {
						if (!r.exc) {
							if (!args.against_default_supplier) {
								frappe.model.sync(r.message);
								frappe.set_route("Form", r.message.doctype, r.message.name);
							} else {
								frappe.route_options = {
									sales_order: me.frm.doc.name,
								};
								frappe.set_route("List", "Purchase Order");
							}
						}
					},
				});
			},
		});

		dialog.fields_dict["against_default_supplier"].df.onchange = () => set_po_items_data(dialog);

		function set_po_items_data(dialog) {
			var against_default_supplier = dialog.get_value("against_default_supplier");
			var items_for_po = dialog.get_value("items_for_po");

			if (against_default_supplier) {
				let items_with_supplier = items_for_po.filter((item) => item.supplier);

				dialog.fields_dict["items_for_po"].df.data = items_with_supplier;
				dialog.get_field("items_for_po").refresh();
			} else {
				let po_items = [];
				me.frm.doc.items.forEach((d) => {
					let ordered_qty = me.get_ordered_qty(d, me.frm.doc);
					let pending_qty = (flt(d.stock_qty) - ordered_qty) / flt(d.conversion_factor);
					if (pending_qty > 0) {
						po_items.push({
							doctype: "Sales Order Item",
							name: d.name,
							item_name: d.item_name,
							item_code: d.item_code,
							pending_qty: pending_qty,
							uom: d.uom,
							supplier: d.supplier,
						});
					}
				});

				dialog.fields_dict["items_for_po"].df.data = po_items;
				dialog.get_field("items_for_po").refresh();
			}
		}

		set_po_items_data(dialog);
		dialog.get_field("items_for_po").grid.only_sortable();
		dialog.get_field("items_for_po").refresh();
		dialog.wrapper.find(".grid-heading-row .grid-row-check").click();
		dialog.show();
	}

	get_ordered_qty(item, so) {
		let ordered_qty = item.ordered_qty;
		if (so.packed_items && so.packed_items.length) {
			// calculate ordered qty based on packed items in case of product bundle
			let packed_items = so.packed_items.filter((pi) => pi.parent_detail_docname == item.name);
			if (packed_items && packed_items.length) {
				ordered_qty = packed_items.reduce((sum, pi) => sum + flt(pi.ordered_qty), 0);
				ordered_qty = ordered_qty / packed_items.length;
			}
		}
		return ordered_qty;
	}

	hold_sales_order() {
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __("Reason for Hold"),
			fields: [
				{
					fieldname: "reason_for_hold",
					fieldtype: "Text",
					reqd: 1,
				},
			],
			primary_action: function () {
				var data = d.get_values();
				frappe.call({
					method: "frappe.desk.form.utils.add_comment",
					args: {
						reference_doctype: me.frm.doctype,
						reference_name: me.frm.docname,
						content: __("Reason for hold:") + " " + data.reason_for_hold,
						comment_email: frappe.session.user,
						comment_by: frappe.session.user_fullname,
					},
					callback: function (r) {
						if (!r.exc) {
							me.update_status("Hold", "On Hold");
							d.hide();
						}
					},
				});
			},
		});
		d.show();
	}
	close_sales_order() {
		this.frm.cscript.update_status("Close", "Closed");
	}
	update_status(label, status) {
		var doc = this.frm.doc;
		var me = this;
		frappe.ui.form.is_saving = true;
		frappe.call({
			method: "erpnext.selling.doctype.sales_order.sales_order.update_status",
			args: { status: status, name: doc.name },
			callback: function (r) {
				me.frm.reload_doc();
			},
			always: function () {
				frappe.ui.form.is_saving = false;
			},
		});
	}
};

// Sales Team event handlers
frappe.ui.form.on("Sales Team", {
	merator: function(frm, cdt, cdn) {
		calculate_allocated_percentage(frm, cdt, cdn);
	},
	denominator: function(frm, cdt, cdn) {
		calculate_allocated_percentage(frm, cdt, cdn);
	}
});

function calculate_allocated_percentage(frm, cdt, cdn) {
	var row = locals[cdt][cdn];

	if (row.merator && row.denominator && row.denominator > 0) {
		// Calculate percentage from merator/denominator
		var percentage = (row.merator / row.denominator) * 100;
		frappe.model.set_value(cdt, cdn, "allocated_percentage", percentage);
	}
}

// Helper to decode unicode escape sequences (e.g. B\u00f4ng Tai -> Bông Tai)
function decode_unicode(str) {
	return str.replace(/\\u[\dA-F]{4}/gi, 
		(match) => String.fromCharCode(parseInt(match.replace(/\\u/g, ''), 16))
	);
}

extend_cscript(cur_frm.cscript, new erpnext.selling.SalesOrderController({ frm: cur_frm }));
