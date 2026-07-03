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
			let color;
			if (!doc.qty && frm.doc.has_unit_price_items) {
				color = "yellow";
			} else if (doc.stock_qty <= doc.actual_qty) {
				color = "green";
			} else {
				color = "orange";
			}

			return color;
		});

		frm.set_query("bom_no", "items", function (doc, cdt, cdn) {
			var row = locals[cdt][cdn];
			return {
				filters: {
					item: row.item_code,
				},
			};
		});

		frm.set_query("sales_person", "sales_team", function () {
			return {
				filters: {
					is_group: 0,
					enabled: 1,
				},
			};
		});

		frm.set_df_property("packed_items", "cannot_add_rows", true);
		frm.set_df_property("packed_items", "cannot_delete_rows", true);
	},
	delivery_date(frm) {
		if (frm.doc.delivery_date) {
			frm.doc.items.forEach((d) => {
				frappe.model.set_value(d.doctype, d.name, "delivery_date", frm.doc.delivery_date);
			});
		}
	},
	validate: function (frm) {
		if (frm.is_new()) return;

		if (frm._promo_validated) {
			frm._promo_validated = false;
			return;
		}

		let message = "";
		(frm.doc.items || []).forEach(item => {
			if (erpnext.utils.item.isJewelryItem(item)) {
				if (!item.serial_numbers) {
					message = __("Chưa nhập serial number cho sản phẩm {0}", [item.item_name]);
				}
			}
		});

		if (message) {
			frappe.msgprint(message);
			frappe.validated = false;
			return;
		}

		// Validate product_availability_status is set on all items
		let missing_availability = (frm.doc.items || []).filter(item => {
			if (!item.product_availability_status) {
				if (erpnext.utils.item.isWarrantyItem(item) || erpnext.utils.item.isGiftItemByName(item)) {
					return false;
				}
				return true;
			}
			return false;
		});
		if (missing_availability.length) {
			frappe.validated = false;

			let item_rows_html = missing_availability.map((item, i) => {
				let safe_name = frappe.utils.escape_html(item.item_name || item.item_code);
				return `<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid #f0f0f0;">
					<span style="flex:1;font-weight:600;color:#333;font-size:13px;">${i + 1}. ${safe_name}</span>
					<div style="display:flex;gap:16px;flex-shrink:0;">
						<label style="display:flex;align-items:center;gap:5px;cursor:pointer;font-size:13px;color:#555;">
							<input type="radio" name="avail_${i}" value="In Stock" style="cursor:pointer;"> ${__("In Stock")}
						</label>
						<label style="display:flex;align-items:center;gap:5px;cursor:pointer;font-size:13px;color:#555;">
							<input type="radio" name="avail_${i}" value="Pre-order" style="cursor:pointer;"> ${__("Pre-order")}
						</label>
					</div>
				</div>`;
			}).join("");

			let d = new frappe.ui.Dialog({
				title: __("Thiếu trạng thái tồn kho sản phẩm"),
				fields: [
					{
						fieldtype: "HTML",
						options: `<div style="margin-bottom:4px;">
							<div style="color:#555;margin-bottom:8px;font-size:13px;">Vui lòng chọn <b>Trạng thái tồn kho</b> cho từng sản phẩm:</div>
							<div>${item_rows_html}</div>
						</div>`
					}
				],
				primary_action_label: __("Áp dụng & Lưu"),
				primary_action() {
					let all_set = missing_availability.every((item, i) =>
						d.$wrapper.find(`input[name="avail_${i}"]:checked`).length > 0
					);
					if (!all_set) {
						frappe.msgprint(__("Vui lòng chọn trạng thái cho tất cả sản phẩm."));
						return;
					}
					missing_availability.forEach((item, i) => {
						let val = d.$wrapper.find(`input[name="avail_${i}"]:checked`).val();
						frappe.model.set_value(item.doctype, item.name, "product_availability_status", val);
					});
					d.hide();
					frm.save();
				},
				secondary_action_label: __("Tự điền thủ công"),
				secondary_action() {
					d.hide();
				}
			});
			d.show();
			return;
		}

		var items_with_promos = (frm.doc.items || []).filter(item => parse_promos(item.new_promotions).length > 0);
		var has_order_promos = (frm.doc.promotions || []).some(row => row.promotion);

		var items_missing_promos = (frm.doc.items || []).filter(function (item) {
			if (parse_promos(item.new_promotions).length > 0) return false;
			if (!item.price_list_rate) return false;
			var diff = Math.abs((item.rate * item.qty) - (item.price_list_rate * item.qty));
			return diff > 5000;
		});

		if (!items_with_promos.length && !has_order_promos && !items_missing_promos.length) return;

		frappe.validated = false;
		let run_price_validation = function () {
			validate_promotion_prices(frm, items_with_promos, items_missing_promos).then(function (errors) {
				if (errors.length) {
					frappe.msgprint({
						title: __("Giá không khớp với khuyến mãi"),
						message: errors.join("<br>"),
						indicator: "red"
					});
				} else {
					frm._promo_validated = true;
					frappe.validated = true;
					frm.save();
				}
			});
		};

		if (items_missing_promos.length > 0 && !frm.is_new()) {
			frappe.call({
				method: "erpnext.selling.doctype.sales_order.sales_order.fetch_promotions_from_split_group",
				args: { sales_order_name: frm.doc.name },
				callback: function (r) {
					let was_updated = false;
					if (r.message && r.message.length > 0) {
						r.message.forEach(data => {
							let row = frappe.get_doc("Sales Order Item", data.name);
							if (row) {
								frappe.model.set_value(row.doctype, row.name, "new_promotions", data.new_promotions);
								was_updated = true;
							}
						});
					}

					if (was_updated) {
						setTimeout(() => frm.save(), 500);
					} else {
						run_price_validation();
					}
				}
			});
		} else {
			run_price_validation();
		}
	},

	onload_post_render: async function(frm) {
		if (erpnext.utils.sales_order_gallery && erpnext.utils.sales_order_gallery.render_gallery) {
			await erpnext.utils.sales_order_gallery.render_gallery(frm);
		}
	},
	attachments_update: async function(frm) {
		if (erpnext.utils.sales_order_gallery && erpnext.utils.sales_order_gallery.render_gallery) {
			await erpnext.utils.sales_order_gallery.render_gallery(frm);
		}
	},
	refresh: function (frm) {
		if (erpnext.utils.sales_order_gallery && erpnext.utils.sales_order_gallery.render_gallery) {
			erpnext.utils.sales_order_gallery.render_gallery(frm);
			erpnext.utils.sales_order_gallery.bind_gallery_listeners(frm);
		}

		frm.fields_dict["items"].grid.update_docfield_property(
			"add_schedule",
			"hidden",
			frm.is_new() || frm.doc.docstatus === 1 ? true : false
		);
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
			frm.add_custom_button(__('View Related Split Orders'), function () {
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
				callback: function (r) {
					if (r.message && r.message.length > 0) {
						// Calculate total of all orders in group
						let total_group_amount = 0;
						let all_orders = r.message;

						all_orders.forEach(function (order) {
							total_group_amount += order.grand_total || 0;
						});

						let html = '<div class="split-orders-info" style="margin-top: 10px; padding: 10px; background-color: #f0f4f7; border-radius: 5px;">';
						html += `<h6 style="margin-bottom: 10px; color: #3498db; font-size: 13px;"><i class="fa fa-link"></i> All Orders in Split Group: <b>${all_orders.length}</b></h6>`;
						html += '<ul style="margin: 0; padding-left: 20px;">';

						all_orders.forEach(function (order) {
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

		frm.add_custom_button(__('View On Haravan'), function () {
			const haravanUrl = `https://jemmiavn.myharavan.com/admin/orders/${frm.doc.haravan_order_id}`;
			window.open(haravanUrl, '_blank');
		});

		frm.add_custom_button(__("Send Order To Lark"), frappe.utils.debounce(() => {
			frappe.db.get_doc("Sales Order", frm.doc.name).then((doc) => {

				const btn = frm.custom_buttons[__("Send Order To Lark")];
				$(btn).prop("disabled", true);

				frappe.call({
					method: "erpnext.selling.doctype.sales_order.sales_order.larksuite_notification",
					args: { sales_order_doc: doc },
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
				query: "erpnext.selling.doctype.promotion.promotion.promotion_query",
				filters: {
					"scope": "Order",
					"transaction_date": frm.doc.transaction_date,
					"real_order_date": frm.doc.real_order_date
				}
			};
		});

		if (frm.doc.docstatus === 1) {
			if (
				frm.doc.status !== "Closed" &&
				flt(frm.doc.per_delivered) < 100 &&
				flt(frm.doc.per_billed) < 100 &&
				frm.has_perm("write") &&
				!frm.doc.is_subcontracted
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
				frappe.model.can_cancel("Stock Reservation Entry") &&
				!frm.doc.is_subcontracted
			) {
				frm.add_custom_button(
					__("Unreserve"),
					() => frm.events.cancel_stock_reservation_entries(frm),
					__("Stock Reservation")
				);
			}

			if (!frm.doc.is_subcontracted) {
				frm.doc.items.forEach((item) => {
					if (
						flt(item.stock_reserved_qty) > 0 &&
						frappe.model.can_read("Stock Reservation Entry")
					) {
						frm.add_custom_button(
							__("Reserved Stock"),
							() => frm.events.show_reserved_stock(frm),
							__("Stock Reservation")
						);
						return;
					}
				});
			}
		}

		if (frm.doc.docstatus === 0) {
			erpnext.set_unit_price_items_note(frm);

			if (frm.doc.is_internal_customer) {
				frm.events.get_items_from_internal_purchase_order(frm);
			}

			if (frm.doc.docstatus === 0 && !frm.doc.is_subcontracted) {
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
		prevent_past_delivery_dates(frm);
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
			frm.fields_dict.buyback_items.$input.off('click').on('click', function () {
				frm.trigger('show_buyback_selector');
			});
		}
		frm.trigger('render_buyback_items');
		frm.trigger('auto_fetch_item_policies');
	},

	trigger_fetch_policy: function (frm, item_name, item_code, show_alert = true) {
		frappe.call({
			method: "erpnext.selling.doctype.sales_order_item.sales_order_item.trigger_manual_webhook",
			args: { item_name: item_name },
			callback: function (r) {
				if (r.message && show_alert) {
					let label = item_code ? __('cho {0}', [item_code]) : '';
					frappe.show_alert(__('Đang tự động lấy thông tin chính sách {0} ...', [label]), 5);
				}
			}
		});
	},

	sync_reference_promotion_by_serial: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.serial_numbers) return;

		const serials = row.serial_numbers.split('\n').map(s => s.trim()).filter(s => s);
		const target_serial = serials[serials.length - 1];

		if (!target_serial) return;

		frappe.call({
			method: "erpnext.selling.doctype.sales_order.sales_order.get_item_promotions_by_serial",
			args: {
				source_order: frm.doc.name,
				target_serial: target_serial
			},
			callback: function (r) {
				if (r.message && r.message.new_promotions) {
					const data = r.message;
					if (data.new_promotions && data.new_promotions !== "[]") {
						frappe.model.set_value(cdt, cdn, 'new_promotions', data.new_promotions);

						if (typeof render_promotion_pills !== "undefined") {
							setTimeout(() => render_promotion_pills(frm, cdt, cdn), 100);
						}
					}
				}
				frm.refresh_field('items');
			}
		});
	},

	auto_fetch_item_policies: function (frm) {
		if (frm.doc.docstatus !== 0 || frm.doc.__islocal) return;

		let items_to_fetch = frm.doc.items.filter(item => {
			let is_new = item.__islocal ||
				(item.name && (item.name.startsWith("New ") || item.name.startsWith("new-")));
			return !is_new && !item.item_policy && item.is_policy_locked !== 1;
		});

		if (items_to_fetch.length > 0) {
			items_to_fetch.forEach(item => {
				frm.events.trigger_fetch_policy(frm, item.name, item.item_code, false);
			});
		}
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
			callback: function (r) {
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
				d.$wrapper.find('input[type="checkbox"]:checked').each(function () {
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
					callback: function (r) {
						if (r.message && r.message.success) {
							frappe.show_alert({
								message: __('Successfully linked {0} buyback item(s)', [r.message.count]),
								indicator: 'green'
							});
							d.hide();
							frm.reload_doc();
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
			let s = frappe.format(val, { fieldtype: 'Currency', currency: doc.currency });
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
		d.$wrapper.find('.buyback-item-checkbox').on('change', function () {
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
			callback: function (r) {
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
						let s = frappe.format(val, { fieldtype: 'Currency', currency: doc.currency });
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
							frm.fields_dict.buyback_items_html.$wrapper.find('.btn-unlink-buyback').off('click').on('click', function (e) {
								e.preventDefault();
								const item_name = $(this).data('item-name');

								frappe.confirm(
									__('Are you sure you want to unlink this buyback item?'),
									() => {
										frappe.call({
											method: 'erpnext.selling.doctype.sales_order.sales_order.unlink_buyback_item',
											args: { item_name: item_name },
											callback: function (r) {
												if (r.message && r.message.success) {
													frappe.show_alert({
														message: __('Buyback item unlinked successfully'),
														indicator: 'green'
													});
													frm.reload_doc();
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
				filters: [
					["Warehouse", "company", "in", ["", cstr(frm.doc.company)]],
					["Warehouse", "is_group", "=", 0],
				],
			};
		});

		frm.set_query("warehouse", "items", function (doc, cdt, cdn) {
			let row = locals[cdt][cdn];
			let query = {
				filters: [
					["Warehouse", "company", "in", ["", cstr(frm.doc.company)]],
					["Warehouse", "is_group", "=", 0],
				],
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
			"Delivery Schedule Item",
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

	prepare_delivery_schedule(frm, row, data) {
		let fields = [
			{
				fieldtype: "Date",
				fieldname: "delivery_date",
				label: __("First Delivery Date"),
				reqd: 1,
				default: row.delivery_date || frm.doc.delivery_date || frappe.datetime.get_today(),
			},
			{
				fieldtype: "Float",
				fieldname: "qty",
				label: __("Qty"),
				read_only: 1,
				default: row.qty || 0,
			},
			{
				fieldtype: "Column Break",
			},
			{
				fieldtype: "Select",
				fieldname: "frequency",
				label: __("Frequency"),
				options: "\nWeekly\nMonthly\nQuarterly\nHalf Yearly\nYearly",
			},
			{
				fieldtype: "Int",
				fieldname: "no_of_deliveries",
				label: __("No of Deliveries"),
			},
			{
				fieldtype: "Section Break",
			},
			{
				fieldtype: "Button",
				fieldname: "get_delivery_schedule",
				label: __("Get Delivery Schedule"),
				click: () => {
					frappe.db.get_value("UOM", row.uom, "must_be_whole_number", (r) => {
						frm.events.add_delivery_schedule(frm, row, r.must_be_whole_number);
					});
				},
			},
			{
				fieldtype: "Table",
				data: [],
				fieldname: "delivery_schedule",
				label: __("Delivery Schedule"),
				fields: [
					{
						fieldtype: "Date",
						fieldname: "delivery_date",
						label: __("Delivery Date"),
						reqd: 1,
						in_list_view: 1,
					},
					{
						fieldtype: "Float",
						fieldname: "qty",
						label: __("Qty"),
						reqd: 1,
						in_list_view: 1,
					},
					{
						fieldtype: "Data",
						fieldname: "Name",
						label: __("name"),
						read_only: 1,
					},
				],
			},
		];

		frm.schedule_dialog = new frappe.ui.Dialog({
			title: __("Delivery Schedule"),
			fields: fields,
			size: "large",
			primary_action_label: __("Add Schedule"),
			primary_action: (data) => {
				if (!data.delivery_schedule || !data.delivery_schedule.length) {
					frappe.throw(__("Please enter at least one delivery date and quantity"));
				}

				let total_qty = 0;
				data.delivery_schedule.forEach((d) => {
					if (!d.qty) {
						frappe.throw(__("Please enter a valid quantity"));
					}
					total_qty += flt(d.qty);
				});

				if (total_qty > flt(row.qty)) {
					frappe.throw(
						__("Total quantity in delivery schedule cannot be greater than the item quantity")
					);
				}

				frappe.call({
					doc: frm.doc,
					method: "create_delivery_schedule",
					args: {
						child_row: row,
						schedules: data.delivery_schedule,
					},
					freeze: true,
					freeze_message: __("Creating Delivery Schedule..."),
					callback: function () {
						frm.refresh_field("items");
						frm.schedule_dialog.hide();
					},
				});
			},
		});

		frm.schedule_dialog.show();

		if (data?.length) {
			data.forEach((d) => {
				if (d.delivery_date && d.qty) {
					frm.schedule_dialog.fields_dict.delivery_schedule.df.data.push({
						delivery_date: d.delivery_date,
						qty: d.qty,
						name: d.name,
					});
				}
			});

			frm.schedule_dialog.fields_dict.delivery_schedule.refresh();
		}
	},

	add_delivery_schedule(frm, row, must_be_whole_number) {
		let first_delivery_date = frm.schedule_dialog.get_value("delivery_date");
		let frequency = frm.schedule_dialog.get_value("frequency");
		let no_of_deliveries = cint(frm.schedule_dialog.get_value("no_of_deliveries"));

		if (!frequency) {
			frappe.throw(__("Please select a frequency for delivery schedule"));
		}

		if (!first_delivery_date) {
			frappe.throw(__("Please enter the first delivery date"));
		}

		if (no_of_deliveries <= 0) {
			frappe.throw(__("Please enter a valid number of deliveries"));
		}

		frm.schedule_dialog.fields_dict.delivery_schedule.df.data = [];
		let qty_to_deliver = row.qty;
		let qty_per_delivery = qty_to_deliver / no_of_deliveries;
		for (let i = 0; i < no_of_deliveries; i++) {
			let qty = qty_per_delivery;
			if (must_be_whole_number) {
				qty = cint(qty);
			}

			if (i === no_of_deliveries - 1) {
				// Last delivery, adjust the quantity to deliver the remaining amount
				qty = qty_to_deliver;
				qty_to_deliver = 0;
			} else {
				qty_to_deliver -= qty;
			}

			frm.schedule_dialog.fields_dict.delivery_schedule.df.data.push({
				delivery_date: first_delivery_date,
				qty: qty,
			});

			if (frequency === "Weekly") {
				first_delivery_date = frappe.datetime.add_days(first_delivery_date, i + 1 * 7);
			} else {
				let month_mapper = {
					Monthly: 1,
					Quarterly: 3,
					Half_Yearly: 6,
					Yearly: 12,
				};

				first_delivery_date = frappe.datetime.add_months(
					first_delivery_date,
					month_mapper[frequency] * i + 1
				);
			}
		}

		frm.schedule_dialog.fields_dict.delivery_schedule.refresh();
	},

	set_delivery_schedule(frm, row, data) {
		data.forEach((d) => {
			if (d.delivery_date && d.qty) {
				frm.schedule_dialog.fields_dict.delivery_schedule.df.data.push({
					delivery_date: d.delivery_date,
					qty: d.qty,
				});
			}
		});

		frm.schedule_dialog.fields_dict.delivery_schedule.refresh();
	},

	get_subcontracting_boms_for_finished_goods: function (fg_item) {
		return frappe.call({
			method: "erpnext.subcontracting.doctype.subcontracting_bom.subcontracting_bom.get_subcontracting_boms_for_finished_goods",
			args: {
				fg_items: fg_item,
			},
		});
	},

	get_subcontracting_boms_for_service_item: function (service_item) {
		return frappe.call({
			method: "erpnext.subcontracting.doctype.subcontracting_bom.subcontracting_bom.get_subcontracting_boms_for_service_item",
			args: {
				service_item: service_item,
			},
		});
	},
});

frappe.ui.form.on("Sales Order Item", {
	item_code: async function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (frm.doc.delivery_date) {
			row.delivery_date = frm.doc.delivery_date;
			refresh_field("delivery_date", cdn, "items");
		} else {
			frm.script_manager.copy_from_first_row("items", row, ["delivery_date"]);
		}

		if (frm.doc.is_subcontracted) {
			if (row.item_code && !row.fg_item) {
				var result = await frm.events.get_subcontracting_boms_for_service_item(row.item_code);

				if (result.message && Object.keys(result.message).length) {
					var finished_goods = Object.keys(result.message);

					// Set FG if only one active Subcontracting BOM is found
					if (finished_goods.length === 1) {
						row.fg_item = result.message[finished_goods[0]].finished_good;
						row.uom = result.message[finished_goods[0]].finished_good_uom;
						refresh_field("items");
					} else {
						const dialog = new frappe.ui.Dialog({
							title: __("Select Finished Good"),
							size: "small",
							fields: [
								{
									fieldname: "finished_good",
									fieldtype: "Autocomplete",
									label: __("Finished Good"),
									options: finished_goods,
								},
							],
							primary_action_label: __("Select"),
							primary_action: () => {
								var subcontracting_bom = result.message[dialog.get_value("finished_good")];

								if (subcontracting_bom) {
									row.fg_item = subcontracting_bom.finished_good;
									row.uom = subcontracting_bom.finished_good_uom;
									refresh_field("items");
								}

								dialog.hide();
							},
						});

						dialog.show();
					}
				}
			}
		}
	},

	delivery_date: function (frm, cdt, cdn) {
		if (!frm.doc.delivery_date) {
			erpnext.utils.copy_value_in_all_rows(frm.doc, cdt, cdn, "items", "delivery_date");
		}
	},

	add_schedule(frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		if (row.__islocal) {
			frappe.throw(__("Please save the Sales Order before adding a delivery schedule."));
		}

		frappe.call({
			method: "get_delivery_schedule",
			doc: frm.doc,
			args: {
				sales_order_item: row.name,
			},
			callback: function (r) {
				frm.events.prepare_delivery_schedule(frm, row, r.message);
			},
		});
	},

	fg_item: async function (frm, cdt, cdn) {
		if (frm.doc.is_subcontracted) {
			var row = locals[cdt][cdn];

			if (row.fg_item) {
				var result = await frm.events.get_subcontracting_boms_for_finished_goods(row.fg_item);

				if (result.message && Object.keys(result.message).length) {
					frappe.model.set_value(cdt, cdn, "item_code", result.message.service_item);
					frappe.model.set_value(
						cdt,
						cdn,
						"qty",
						flt(row.fg_item_qty) * flt(result.message.conversion_factor)
					);
					frappe.model.set_value(cdt, cdn, "uom", result.message.service_item_uom);
				}
			}
		}
	},

	qty: async function (frm, cdt, cdn) {
		if (frm.doc.is_subcontracted) {
			var row = locals[cdt][cdn];

			if (row.fg_item) {
				var result = await frm.events.get_subcontracting_boms_for_finished_goods(row.fg_item);

				if (
					result.message &&
					row.item_code == result.message.service_item &&
					row.uom == result.message.service_item_uom
				) {
					frappe.model.set_value(
						cdt,
						cdn,
						"fg_item_qty",
						flt(row.qty) / flt(result.message.conversion_factor)
					);
				}
			}
		}
	},

	fetch_policy: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		frm.events.trigger_fetch_policy(frm, row.name, row.item_code, true);
	},

	serial: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (row.serial) {
			if (!erpnext.utils.item.isJewelryItem(row)) {
				frappe.msgprint({
					title: __("Không hỗ trợ Serial"),
					indicator: "orange",
					message: __("Chỉ sản phẩm Trang sức mới sử dụng số Serial.")
				});
				frappe.model.set_value(cdt, cdn, 'serial', null);
				return;
			}

			const val = row.serial;
			frappe.call({
				method: "erpnext.selling.doctype.sales_order.sales_order.validate_serial_number",
				args: {
					serial_number: val,
					sales_order_name: frm.doc.name
				},
				callback: function (r) {
					if (r.message && !r.message.allowed) {
						frappe.msgprint({
							title: __("Trùng số Serial"),
							indicator: "red",
							message: __("Số Serial <b>{0}</b> đã được điền trong Đơn hàng <b>{1}</b>.", [val, r.message.duplicate_order])
						});
						frappe.model.set_value(cdt, cdn, 'serial', null);
						return;
					}

					const current_serials = row.serial_numbers ? row.serial_numbers.split('\n') : [];
					if (!current_serials.includes(val)) {
						const new_list = row.serial_numbers ? `${row.serial_numbers}\n${val}` : val;
						frappe.model.set_value(cdt, cdn, 'serial_numbers', new_list.replace(/\n+/g, '\n').trim());
					}

					frappe.model.set_value(cdt, cdn, 'serial', null);

					if ((frm.doc.haravan_ref_order_id || frm.doc.split_order_group) && (!row.new_promotions || row.new_promotions == "[]")) {
						frm.events.sync_reference_promotion_by_serial(frm, cdt, cdn);
					}

					frappe.db.get_value('Serial', val, 'serial_number').then((r) => {
						if (r && r.message && r.message.serial_number && r.message.serial_number !== val) {
							const official = r.message.serial_number;
							const updated = row.serial_numbers.split('\n').map(s => s === val ? official : s);
							frappe.model.set_value(cdt, cdn, 'serial_numbers', updated.join('\n'));
						}
					});
				}
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
	setup(doc) {
		this.setup_accounting_dimension_triggers();
		super.setup(doc);
	}
	onload(doc, dt, dn) {
		super.onload(doc, dt, dn);
	}

	refresh(doc, dt, dn) {
		var me = this;
		super.refresh();
		let allow_delivery = false;

		if (doc.docstatus == 1) {
			if (
				!["Closed", "Completed"].includes(doc.status) &&
				flt(doc.per_delivered) < 100 &&
				flt(doc.per_billed) < 100
			) {
				if (!doc.__onload || doc.__onload.can_update_items) {
					this.frm.add_custom_button(__("Update Items"), () => {
						erpnext.utils.update_child_items({
							frm: this.frm,
							child_docname: "items",
							child_doctype: "Sales Order Detail",
							cannot_add_row: false,
						});
					});
				}
			}
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
					const items_are_deliverable = this.frm.doc.items.some(
						(item) => item.delivered_by_supplier === 0 && item.qty > flt(item.delivered_qty)
					);
					allow_delivery =
						(this.frm.doc.has_unit_price_items || items_are_deliverable) &&
						!this.frm.doc.skip_delivery_note;

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

					if (doc.is_subcontracted) {
						if (!doc.items.every((item) => item.qty == item.subcontracted_qty)) {
							this.frm.add_custom_button(
								__("Subcontracting Inward Order"),
								() => {
									me.make_subcontracting_inward_order();
								},
								__("Create")
							);
						}
					}

					if (
						(!doc.__onload || !doc.__onload.has_reserved_stock) &&
						flt(doc.per_picked) < 100 &&
						flt(doc.per_delivered) < 100 &&
						frappe.model.can_create("Pick List") &&
						!doc.is_subcontracted
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

						if (frappe.model.can_create("Work Order") && !doc.is_subcontracted) {
							this.frm.add_custom_button(
								__("Work Order"),
								() => this.make_work_order(),
								__("Create")
							);
						}
					}

					// sales invoice
					if (
						(flt(doc.per_billed) < 100 && frappe.model.can_create("Sales Invoice")) ||
						doc.is_subcontracted
					) {
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
						frappe.model.can_create("Material Request") &&
						!doc.is_subcontracted
					) {
						if (!doc.is_subcontracted) {
							this.frm.add_custom_button(
								__("Material Request"),
								() => this.make_material_request(),
								__("Create")
							);
						}
						this.frm.add_custom_button(
							__("Request for Raw Materials"),
							() => this.make_raw_material_request(),
							__("Create")
						);
					}

					// Make Purchase Order
					if (
						!this.frm.doc.is_internal_customer &&
						frappe.model.can_create("Purchase Order") &&
						!doc.is_subcontracted
					) {
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
									? __("Internal Purchase Order")
									: __("Inter Company Purchase Order");

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
						() => this.make_payment_request_with_schedule(),
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
				if (r.message.length === 0) {
					frappe.msgprint({
						title: __("Work Order not created"),
						message: __(
							"No Items with Bill of Materials to Manufacture or all items already manufactured"
						),
						indicator: "orange",
					});
					return;
				} else {
					const fields = [
						{
							label: __("Items"),
							fieldtype: "Table",
							fieldname: "items",
							cannot_add_rows: true,
							description: __("Select BOM and Qty for Production"),
							fields: [
								{
									fieldtype: "Link",
									fieldname: "item_code",
									options: "Item",
									label: __("Item Code"),
									in_list_view: 1,
									read_only: 1,
								},
								{
									fieldtype: "Data",
									fieldname: "item_name",
									label: __("Item Name"),
									in_list_view: 1,
									read_only: 1,
									fetch_from: "item_code.item_name",
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
									read_only: 1,
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
							if (!data.items.length) {
								frappe.throw(__("Please select atleast one item to continue"));
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
						project: me.frm.doc.project,
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

		var today = new Date();

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
								<input
									type="checkbox"
									data-date="${date}"
									${frappe.datetime.get_day_diff(new Date(date), today) > 0 ? "" : 'checked="checked"'}
								/>
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
			const pending_qty = flt(item.stock_qty) - this.get_ordered_qty(item, this.frm.doc);
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
					fieldname: "set_supplier",
					fieldtype: "Link",
					label: __("Set Supplier"),
					options: "Supplier",
					onchange: function () {
						let supplier = dialog.get_value("set_supplier");
						let items_table = dialog.fields_dict.items_for_po.grid;
						let selected_items = items_table.get_selected_children();

						selected_items.forEach((item) => {
							item.supplier = supplier;
							items_table.refresh();
						});
					},
				},
				{
					fieldtype: "Column Break",
				},
				{
					fieldtype: "Section Break",
				},
				{
					fieldname: "items_for_po",
					fieldtype: "Table",
					label: __("Select Items"),
					cannot_add_rows: true,
					cannot_delete_rows: true,
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
							options: "UOM",
							in_list_view: 1,
						},
						{
							fieldtype: "Link",
							fieldname: "supplier",
							label: __("Supplier"),
							reqd: 1,
							options: "Supplier",
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

				if (selected_items.some((item) => !item.supplier)) {
					frappe.throw({
						message: __("Supplier is required for all selected Items"),
						title: __("Supplier Required"),
						indicator: "blue",
					});
				}

				dialog.hide();
				return frappe.call({
					method: "erpnext.selling.doctype.sales_order.sales_order.make_purchase_order",
					freeze_message: __("Creating Purchase Order ..."),
					args: {
						source_name: me.frm.doc.name,
						selected_items: selected_items,
					},
					freeze: true,
					callback: function (r) {
						if (!r.exc) {
							if (r.message.length == 1) {
								frappe.model.sync(r.message[0]);
								frappe.set_route("Form", r.message[0].doctype, r.message[0].name);
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

		function set_po_items_data(dialog) {
			let po_items = [];
			me.frm.doc.items.forEach((d) => {
				let ordered_qty = me.get_ordered_qty(d, me.frm.doc);
				let pending_qty = (flt(d.stock_qty) - ordered_qty) / flt(d.conversion_factor);
				if (pending_qty > 0) {
					po_items.push({
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

		set_po_items_data(dialog);
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
				const all_packed_items_ordered = packed_items.every(
					(pi) => flt(pi.ordered_qty) >= flt(pi.qty)
				);
				ordered_qty = all_packed_items_ordered ? item.stock_qty : 0;
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

	make_subcontracting_inward_order() {
		frappe.model.open_mapped_doc({
			method: "erpnext.selling.doctype.sales_order.sales_order.make_subcontracting_inward_order",
			frm: this.frm,
			freeze_message: __("Creating Subcontracting Inward Order ..."),
		});
	}
};

// Sales Team event handlers
frappe.ui.form.on("Sales Team", {
	merator: function (frm, cdt, cdn) {
		calculate_allocated_percentage(frm, cdt, cdn);
	},
	denominator: function (frm, cdt, cdn) {
		calculate_allocated_percentage(frm, cdt, cdn);
	}
});

// Order and Debt Tracking event handlers
frappe.ui.form.on("Order and Debt Tracking", {
	progress_status: function (frm, cdt, cdn) {
		set_reason_options(frm, cdt, cdn);
	},
	form_render: function (frm, cdt, cdn) {
		set_reason_options(frm, cdt, cdn);
	},
	debt_history_add: function (frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "date", frappe.datetime.get_today());
		frappe.model.set_value(cdt, cdn, "added_by", frappe.session.user);
		let default_options = [
			"Khách đã chốt ngày đến nhận tại cửa hàng",
			"Sale sẽ giao tận nơi cho khách",
			"Gửi đơn vị vận chuyển (COD) về địa chỉ khách"
		];
		frm.fields_dict['debt_history'].grid.update_docfield_property('status_reason', 'options', default_options.join('\n'));
	}
});

function set_reason_options(frm, cdt, cdn) {
	let row = locals[cdt][cdn];

	let valid_reasons = {
		"Đủ hàng – khách sẽ nhận tuần tới": [
			"Khách đã chốt ngày đến nhận tại cửa hàng",
			"Sale sẽ giao tận nơi cho khách",
			"Gửi đơn vị vận chuyển (COD) về địa chỉ khách"
		],
		"Đủ hàng – khách chưa chốt ngày nhận": [
			"Khách chưa hẹn ngày nhận cụ thể, sale đang care thêm",
			"Khách bận (công tác, nước ngoài, du lịch...)",
			"Khách chưa đủ tiền / đang gom tiền",
			"Đơn quá hạn công nợ, đã làm đề xuất gia hạn"
		],
		"Chưa đủ hàng": [
			"Đang gia công",
			"Đợi quà tặng",
			"Khách chờ nhận cùng các đơn khác",
			"Hàng lỗi, đang bảo hành tại xưởng"
		],
		"Đã giao – chưa thu đủ tiền": [
			"Đã giao hàng nhưng chưa thanh toán đủ (quản lý đã duyệt)",
			"Chờ đơn vị vận chuyển trả tiền COD",
			"Chờ hoàn tất thủ tục thu đổi"
		]
	};

	let options = valid_reasons[row.progress_status] || [""];

	if (frm.fields_dict['debt_history'] && frm.fields_dict['debt_history'].grid) {
		frm.fields_dict['debt_history'].grid.update_docfield_property('status_reason', 'options', options.join('\n'));
	}

	if (!options.includes(row.status_reason)) {
		frappe.model.set_value(cdt, cdn, 'status_reason', options[0]);
	}
}

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

function prevent_past_delivery_dates(frm) {
	if (frm.doc.transaction_date) {
		frm.fields_dict["delivery_date"].datepicker?.update({
			minDate: new Date(frm.doc.transaction_date),
		});
	}
}

function apply_promo_discount(price, p, scope) {
	if (!p) return price;

	if (scope === "Line Item") {
		if (p.priority === "G0") return price;
		if (p.priority === "G1") {
			return price * (1 - (p.discount_percent || 0) / 100);
		}
		if (p.priority === "G2") {
			return price - (p.discount_amount || 0);
		}
		if (p.priority === "G3" || p.priority === "G6" || p.priority === "G7" || p.priority === "G4") {
			if (p.discount_type === "Percentage") {
				return price * (1 - (p.discount_percent || 0) / 100);
			} else if (p.discount_type === "Fix Amount") {
				return price - (p.discount_amount || 0);
			}
			return price;
		}
	}

	if (scope === "Order") {
		if (p.priority === "G4") {
			return price - (p.discount_amount || 0);
		}
		if (p.priority === "G5") {
			return price * (1 - (p.discount_percent || 0) / 100);
		}
		if (p.priority === "G6" || p.priority === "G7") {
			if (p.discount_type === "Percentage") {
				return price * (1 - (p.discount_percent || 0) / 100);
			} else if (p.discount_type === "Fix Amount") {
				return price - (p.discount_amount || 0);
			}
			return price;
		}
	}

	return price;
}

function fetch_promo_map(names) {
	return new Promise(function (resolve) {
		if (!names || !names.length) { resolve({}); return; }
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Promotion",
				filters: { name: ["in", names] },
				fields: ["name", "title", "priority", "discount_type", "discount_amount", "discount_percent"],
				limit_page_length: 0
			},
			callback: function (r) {
				var map = {};
				(r.message || []).forEach(function (p) { map[p.name] = p; });
				resolve(map);
			}
		});
	});
}

function validate_promotion_prices(frm, items, items_missing_promos) {
	var all_promo_names = [];

	items.forEach(function (item) {
		parse_promos(item.new_promotions).forEach(function (p) {
			if (!all_promo_names.includes(p)) all_promo_names.push(p);
		});
	});

	var order_promo_names = (frm.doc.promotions || []).map(function (row) { return row.promotion; }).filter(Boolean);
	order_promo_names.forEach(function (p) {
		if (!all_promo_names.includes(p)) all_promo_names.push(p);
	});

	return new Promise(function (resolve) {
		var errors = [];

		(items_missing_promos || []).forEach(function (item) {
			var diff = Math.abs((item.rate * item.qty) - (item.price_list_rate * item.qty));
			errors.push(__("Sản phẩm {0}: giá {1} lệch {2} so với giá niêm yết {3} nhưng chưa chọn khuyến mãi", [
				item.item_name,
				format_currency(item.rate, frm.doc.currency),
				format_currency(diff, frm.doc.currency),
				format_currency(item.price_list_rate, frm.doc.currency)
			]));
		});

		if (!all_promo_names.length) { resolve(errors); return; }

		fetch_promo_map(all_promo_names).then(function (promo_map) {
			items.forEach(function (item) {
				var promos = parse_promos(item.new_promotions);
				if (!promos.length) return;

				var expected = item.price_list_rate || 0;
				var promo_objects = promos.map(function (name) { return promo_map[name]; }).filter(Boolean);
				promo_objects.forEach(function (p) {
					expected = apply_promo_discount(expected, p, "Line Item");
				});

				var diff = Math.abs((item.rate * item.qty) - (expected * item.qty));
				if (diff > 5000) {
					errors.push(__("Sản phẩm {0}: giá thực tế {1} lệch {2} so với giá sau khuyến mãi {3}", [
						item.item_name,
						format_currency(item.rate, frm.doc.currency),
						format_currency(diff, frm.doc.currency),
						format_currency(expected, frm.doc.currency)
					]));
				}
			});

			var base_total = (frm.doc.items || []).reduce(function (sum, item) {
				return sum + (item.rate * item.qty);
			}, 0);
			var expected_total = base_total;
			var order_promo_objects = order_promo_names.map(function (name) { return promo_map[name]; }).filter(Boolean);
			order_promo_objects.forEach(function (p) {
				expected_total = apply_promo_discount(expected_total, p, "Order");
			});
			var order_diff = Math.abs(frm.doc.grand_total - expected_total);
			if (order_diff > 5000) {
				errors.push(__("Tổng đơn hàng: giá thực tế {0} lệch {1} so với giá sau khuyến mãi {2}", [
					format_currency(frm.doc.grand_total, frm.doc.currency),
					format_currency(order_diff, frm.doc.currency),
					format_currency(expected_total, frm.doc.currency)
				]));
			}

			resolve(errors);
		});
	});
}
function parse_promos(val) {
	try { return JSON.parse(val) || []; } catch (e) { return []; }
}

frappe.ui.form.on('Sales Order Item', {
	select_promotions: function (frm, cdt, cdn) {
		var dialog = new frappe.ui.form.MultiSelectDialog({
			doctype: "Promotion",
			target: frm,
			setters: {
				title: null,
			},
			read_only_setters: ["title"],
			primary_action_label: "Add Selected",
			get_query() {
				return {
					query: "erpnext.selling.doctype.promotion.promotion.promotion_query",
					filters: {
						transaction_date: frm.doc.transaction_date,
						real_order_date: frm.doc.real_order_date,
						scope: "Line Item",
						as_dict: 1
					}
				};
			},
			action(selections) {
				var existing = parse_promos(locals[cdt][cdn]["new_promotions"]);
				existing.push(...selections);
				locals[cdt][cdn]["new_promotions"] = JSON.stringify(existing);
				frm.dirty();
				dialog.dialog.$wrapper.modal("hide");
				dialog.dialog.$wrapper.remove();
				$(".modal-backdrop").last().remove();
				$("body").addClass("modal-open");
				var grid_row = frm.fields_dict.items.grid.grid_rows_by_docname[cdn];
				if (grid_row) {
					grid_row.toggle_view(true);
					if (grid_row.grid_form && grid_row.grid_form.fields_dict.select_promotions) {
						$(grid_row.grid_form.fields_dict.select_promotions.wrapper).find(".promo-validation-warning").remove();
					}
					render_promotion_pills(frm, cdt, cdn);
				}
			}
		});

		setTimeout(() => {
			dialog.dialog.get_field("search_term").set_label("Search Promotion Title");
			dialog.dialog.get_secondary_btn().hide();
			dialog.dialog.get_field("title").$wrapper.hide();
			dialog.dialog.$wrapper.on("hidden.bs.modal", function () {
				$(this).remove();
				$(".modal-backdrop").last().remove();
				$("body").addClass("modal-open");
				var grid_row = frm.fields_dict.items.grid.grid_rows_by_docname[cdn];
				if (grid_row) {
					grid_row.toggle_view(true);
					render_promotion_pills(frm, cdt, cdn);
				}
			});
		}, 100);
	},
	form_render: function (frm, cdt, cdn) {
		render_promotion_pills(frm, cdt, cdn);
		var grid_row = frm.fields_dict.items.grid.grid_rows_by_docname[cdn];
		if (grid_row && grid_row.grid_form && grid_row.grid_form.fields_dict.fetch_policy) {
			var $wrapper = $(grid_row.grid_form.fields_dict.fetch_policy.wrapper);
			if (!$wrapper.prev('.promo-guidance').length) {
				$('<div class="promo-guidance" style="margin-bottom:20px;font-size:12px;color:#666;">' +
					'<b>Lưu ý:</b><br>' +
					'Mỗi CTKM chỉ áp dụng cho sản phẩm đơn chiếc nên cần lưu ý trong trường hợp sản phẩm là <b>Bông Tai</b>:<br>' +
					'- <b>Đối với Sản phẩm tạm:</b> Chọn 02 mã CTKM (tương ứng cho 02 chiếc đơn lẻ cấu thành một cặp). (ví dụ: với SPT giảm 2tr, chọn 2 voucher giảm 1tr)<br>' +
					'- <b>Đối với Sản phẩm tồn kho:</b> Chỉ chọn duy nhất 01 CTKM. (ví dụ, với Bông Tai giảm 1tr, chỉ chọn 1 voucher giảm 500.000)<br><br>' +
					'Nếu không tìm thấy, liên hệ Marketing để được hỗ trợ' +
					'</div>').insertBefore($wrapper);
			}
		}
	},
	rate: function (frm, cdt, cdn) {
		render_promotion_pills(frm, cdt, cdn);
	},
	price_list_rate: function (frm, cdt, cdn) {
		render_promotion_pills(frm, cdt, cdn);
	},
	qty: function (frm, cdt, cdn) {
		render_promotion_pills(frm, cdt, cdn);
	}
});

function render_promotion_pills(frm, cdt, cdn) {
	var promos = parse_promos(locals[cdt][cdn]["new_promotions"]);
	var grid_row = frm.fields_dict.items.grid.grid_rows_by_docname[cdn];
	if (!grid_row || !grid_row.grid_form) return;

	var $field = $(grid_row.grid_form.fields_dict.select_promotions.wrapper);
	$field.find(".promotion-pills").remove();
	if (!promos.length) return;

	var initial_price = locals[cdt][cdn].price_list_rate || 0;

	var $pills = $('<div class="promotion-pills" style="display:flex;flex-direction:column;gap:10px;margin-top:6px;"></div>');
	promos.forEach((promo, idx) => {
		$pills.append($(`<div class="promo-pill" draggable="true" data-promo="${frappe.utils.escape_html(promo)}" data-idx="${idx}" style="background:#f5f5f5;color:#333;padding:8px 14px;border-radius:8px;font-size:13px;display:flex;align-items:center;justify-content:space-between;border:1px solid #d9d9d9;cursor:grab;">
			<div style="display:flex;flex-direction:column;">
				<span class="promo-label" style="font-weight:600;">${frappe.utils.escape_html(promo)}</span>
				<span class="promo-price" style="font-size:12px;color:#1976d2;margin-top:2px;">...</span>
			</div>
			<span class="remove-promo" data-idx="${idx}" style="cursor:pointer;font-size:16px;font-weight:bold;color:#999;margin-left:10px;">&times;</span>
		</div>`));
	});
	$field.append($pills);

	fetch_promo_map(promos).then(function (promo_map) {
		var current_price = initial_price;

		var promo_objects = promos.map(function (name) { return promo_map[name]; }).filter(Boolean);

		promo_objects.forEach(function (p) {
			current_price = apply_promo_discount(current_price, p, "Line Item");
		});

		var running_price = initial_price;
		$pills.find(".promo-pill").each(function () {
			var name = $(this).attr("data-promo");
			var p = promo_map[name];
			if (p) {
				running_price = apply_promo_discount(running_price, p, "Line Item");
				$(this).find(".promo-label").text(p.title || p.name);
				$(this).find(".promo-price").text("Sau khuyến mãi: " + format_currency(running_price, frm.doc.currency).replace(/,00$/, ""));
			} else {
				$(this).find(".promo-price").text("Không tìm thấy trợ giá");
			}
		});

		$field.find(".promo-validation-warning").remove();
		var diff = Math.abs((locals[cdt][cdn].rate * locals[cdt][cdn].qty) - (current_price * locals[cdt][cdn].qty));
		if (current_price >= 0 && diff > 5000) {
			$field.append($(`<div class="promo-validation-warning" style="color:#d32f2f;font-size:12px;margin-top:5px;padding:6px 10px;background:#fdeaea;border-radius:4px;border:1px solid #f5c6c6;"><i class="fa fa-exclamation-triangle"></i> Gi\u00e1 b\u1ecb l\u1ec7ch ${format_currency(diff, frm.doc.currency).replace(/,00$/, "")} so v\u1edbi th\u1ef1c t\u1ebf</div>`));
		} else if (current_price >= 0) {
			$field.append($(`<div class="promo-validation-warning" style="color:#2e7d32;font-size:12px;margin-top:5px;padding:6px 10px;background:#e8f5e9;border-radius:4px;border:1px solid #c8e6c9;"><i class="fa fa-check-circle"></i> Gi\u00e1 kh\u1edbp v\u1edbi gi\u00e1 th\u1ef1c t\u1ebf</div>`));
		}
	});

	$pills.on("click", ".remove-promo", function () {
		var arr = parse_promos(locals[cdt][cdn]["new_promotions"]);
		arr.splice(parseInt($(this).attr("data-idx")), 1);
		frappe.model.set_value(cdt, cdn, "new_promotions", JSON.stringify(arr));
		frm.dirty();
		$field.find(".promo-validation-warning").remove();
		render_promotion_pills(frm, cdt, cdn);
	});

	var drag_src = null;
	$pills.on("dragstart", ".promo-pill", function (e) {
		drag_src = this;
		$(this).css("opacity", "0.4");
		e.originalEvent.dataTransfer.effectAllowed = "move";
	});
	$pills.on("dragover", ".promo-pill", function (e) {
		e.preventDefault();
		$(this).css("border-top", "2px solid #999");
	});
	$pills.on("dragleave", ".promo-pill", function () {
		$(this).css("border-top", "");
	});
	$pills.on("drop", ".promo-pill", function (e) {
		e.preventDefault();
		$(this).css("border-top", "");
		if (drag_src === this) return;
		var arr = parse_promos(locals[cdt][cdn]["new_promotions"]);
		var item = arr.splice(parseInt($(drag_src).attr("data-idx")), 1)[0];
		arr.splice(parseInt($(this).attr("data-idx")), 0, item);
		frappe.model.set_value(cdt, cdn, "new_promotions", JSON.stringify(arr));
		frm.dirty();
		$field.find(".promo-validation-warning").remove();
		render_promotion_pills(frm, cdt, cdn);
	});
	$pills.on("dragend", ".promo-pill", function () {
		$(this).css("opacity", "1");
	});
}
