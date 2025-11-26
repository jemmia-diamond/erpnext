// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Customer", {
	setup: function (frm) {
		frm.make_methods = {
			Quotation: () =>
				frappe.model.open_mapped_doc({
					method: "erpnext.selling.doctype.customer.customer.make_quotation",
					frm: cur_frm,
				}),
			Opportunity: () =>
				frappe.model.open_mapped_doc({
					method: "erpnext.selling.doctype.customer.customer.make_opportunity",
					frm: cur_frm,
				}),
		};

		frm.add_fetch("default_sales_partner", "commission_rate", "default_commission_rate");
		frm.set_query("default_price_list", { selling: 1 });
		frm.set_query("account", "accounts", function (doc, cdt, cdn) {
			let d = locals[cdt][cdn];
			let filters = {
				account_type: "Receivable",
				root_type: "Asset",
				company: d.company,
				is_group: 0,
			};

			if (doc.party_account_currency) {
				$.extend(filters, { account_currency: doc.party_account_currency });
			}
			return {
				filters: filters,
			};
		});

		frm.set_query("advance_account", "accounts", function (doc, cdt, cdn) {
			let d = locals[cdt][cdn];
			return {
				filters: {
					account_type: "Receivable",
					root_type: "Liability",
					company: d.company,
					is_group: 0,
				},
			};
		});

		if (frm.doc.__islocal == 1) {
			frm.set_value("represents_company", "");
		}

		frm.set_query("default_bank_account", function () {
			return {
				filters: {
					is_company_account: 1,
				},
			};
		});

		frm.set_query("user", "portal_users", function () {
			return {
				filters: {
					ignore_user_type: true,
				},
			};
		});

    frm.set_df_property("coupon_table", "cannot_add_rows", true);
    frm.set_df_property("coupon_table", "cannot_delete_rows", true);
	frm.get_field("coupon_table").grid.only_sortable();
	},
	customer_primary_address: function (frm) {
		if (frm.doc.customer_primary_address) {
			frappe.call({
				method: "frappe.contacts.doctype.address.address.get_address_display",
				args: {
					address_dict: frm.doc.customer_primary_address,
				},
				callback: function (r) {
					frm.set_value("primary_address", r.message);
				},
			});
		}
		if (!frm.doc.customer_primary_address) {
			frm.set_value("primary_address", "");
		}
	},

	is_internal_customer: function (frm) {
		if (frm.doc.is_internal_customer == 1) {
			frm.toggle_reqd("represents_company", true);
		} else {
			frm.toggle_reqd("represents_company", false);
		}
	},

	customer_primary_contact: function (frm) {
		if (!frm.doc.customer_primary_contact) {
			frm.set_value("mobile_no", "");
			frm.set_value("email_id", "");
		}
	},

	loyalty_program: function (frm) {
		if (frm.doc.loyalty_program) {
			frm.set_value("loyalty_program_tier", null);
		}
	},

	refresh: function (frm) {
		if (frappe.defaults.get_default("cust_master_name") != "Naming Series") {
			frm.toggle_display("naming_series", false);
		} else {
			erpnext.toggle_naming_series();
		}

		if (!frm.doc.__islocal) {
			if (frm.doc.haravan_id && !frm._priority_loaded) {
				frm._priority_loaded = true;
				setTimeout(() => {
					frappe.call({
						method: "erpnext.selling.doctype.customer.customer.update_customer_priority_data",
						args: {
							customer_name: frm.doc.name,
							haravan_id: frm.doc.haravan_id
						}
					});
				}, 1000);
			}

			if (frm.doc.phone && !frm._buyback_loaded) {
				frm._buyback_loaded = true;
				setTimeout(() => {
					frappe.call({
						method: "erpnext.selling.doctype.customer.customer.load_buyback_records_async",
						args: { customer: frm.doc.name }
					});
				}, 1500);
			}

			if (frm.doc.haravan_id && !frm._coupons_loaded) {
				frm._coupons_loaded = true;
				setTimeout(() => {
					frappe.call({
						method: "erpnext.selling.doctype.coupon.coupon.update_customers_coupons",
						args: {
							customer_name: frm.doc.name,
							customer_haravan_id: parseInt(frm.doc.haravan_id)
						},
						callback: function(r) {
							frm.reload_doc();
						}
					});
				}, 2000);
			}

			frappe.contacts.render_address_and_contact(frm);

			// Load customer orders
			frm.trigger("load_sales_orders");

			frm.add_custom_button(
				__("Accounts Receivable"),
				function () {
					frappe.set_route("query-report", "Accounts Receivable", {
						party_type: "Customer",
						party: frm.doc.name,
					});
				},
				__("View")
			);

			frm.add_custom_button(
				__("Accounting Ledger"),
				function () {
					frappe.set_route("query-report", "General Ledger", {
						party_type: "Customer",
						party: frm.doc.name,
						party_name: frm.doc.customer_name,
					});
				},
				__("View")
			);

			frm.add_custom_button(
				__("Pricing Rule"),
				function () {
					erpnext.utils.make_pricing_rule(frm.doc.doctype, frm.doc.name);
				},
				__("Create")
			);

			frm.add_custom_button(
				__("Get Customer Group Details"),
				function () {
					frm.trigger("get_customer_group_details");
				},
				__("Actions")
			);

			if (cint(frappe.defaults.get_default("enable_common_party_accounting"))) {
				frm.add_custom_button(
					__("Link with Supplier"),
					function () {
						frm.trigger("show_party_link_dialog");
					},
					__("Actions")
				);
			}

			// indicator
			erpnext.utils.set_party_dashboard_indicators(frm);

			var coupon_grid = frm.get_field("coupon_table").grid;
			coupon_grid.cannot_add_rows = true;
			coupon_grid.cannot_delete_rows = true;
			coupon_grid.only_sortable = false;

			frm.fields_dict["coupon_table"].grid.wrapper.find('.grid-remove-rows').hide();
			frm.fields_dict["coupon_table"].grid.wrapper.find('.grid-add-multiple-rows').hide();
			frm.fields_dict["coupon_table"].grid.wrapper.find('.grid-add-row').hide();
			frm.fields_dict("coupon_table").grid.wrapper.find('.grid-move-row').hide();
			frm.fields_dict["coupon_table"].grid.grid_rows.forEach(function (row) {
				row.wrapper.find('.grid-delete-row').hide();
				row.wrapper.find('.grid-duplicate-row').hide();
				row.wrapper.find('.grid-insert-row').hide();
				row.wrapper.find('.grid-insert-row-below').hide();
				row.wrapper.find('.grid-append-row').hide();
			});
			frm.fields_dict["coupon_table"].grid.wrapper.off('click', '.grid-row');
		} else {
			frappe.contacts.clear_address_and_contact(frm);
		}

		var grid = cur_frm.get_field("sales_team").grid;
		grid.set_column_disp("allocated_amount", false);
		grid.set_column_disp("incentives", false);

    frm.set_df_property("coupon_table", "cannot_add_rows", true);
    frm.set_df_property("coupon_table", "cannot_delete_rows", true);
	frm.get_field("coupon_table").grid.only_sortable();
	},
	validate: function (frm) {
		if (frm.doc.lead_name) frappe.model.clear_doc("Lead", frm.doc.lead_name);
	},
	get_customer_group_details: function (frm) {
		frappe.call({
			method: "get_customer_group_details",
			doc: frm.doc,
			callback: function () {
				frm.refresh();
			},
		});
	},
	show_party_link_dialog: function (frm) {
		const dialog = new frappe.ui.Dialog({
			title: __("Select a Supplier"),
			fields: [
				{
					fieldtype: "Link",
					label: __("Supplier"),
					options: "Supplier",
					fieldname: "supplier",
					reqd: 1,
				},
			],
			primary_action: function ({ supplier }) {
				frappe.call({
					method: "erpnext.accounts.doctype.party_link.party_link.create_party_link",
					args: {
						primary_role: "Customer",
						primary_party: frm.doc.name,
						secondary_party: supplier,
					},
					freeze: true,
					callback: function () {
						dialog.hide();
						frappe.msgprint({
							message: __("Successfully linked to Supplier"),
							alert: true,
						});
					},
					error: function () {
						dialog.hide();
						frappe.msgprint({
							message: __("Linking to Supplier Failed. Please try again."),
							title: __("Linking Failed"),
							indicator: "red",
						});
					},
				});
			},
			primary_action_label: __("Create Link"),
		});
		dialog.show();
	},

	load_sales_orders: function(frm) {
		const sales_order_wrapper = frm.get_field("sales_order_html").$wrapper;
		if (!sales_order_wrapper) return;

		sales_order_wrapper.empty();

		// Show loading message
		sales_order_wrapper.html('<div class="text-center"><i class="fa fa-spinner fa-spin"></i> Loading Orders...</div>');

		frappe.call({
			method: 'frappe.client.get_list',
			args: {
				doctype: 'Sales Order',
				filters: {
					'customer': frm.doc.name,
					'cancelled_status': 'Uncancelled'
				},
				fields: ['name', 'order_number', 'transaction_date', 'status', 'grand_total', 'currency', 'haravan_order_id', 'cancelled_status', 'financial_status'],
				order_by: 'transaction_date desc',
				limit_page_length: 20
			},
			callback: function(r) {
				sales_order_wrapper.empty();

				if (r.message && r.message.length > 0) {
					let tabledHeadStyle = "padding: 12px 15px; font-size: 13px; font-weight: 600; color: #6c757d; border: none;";
					let tableDataStyle = "padding: 12px 15px; border: none; vertical-align: middle;";
					let html = `
						<div style="margin-bottom: 10px;">
							<h6 class="text-muted" style="margin: 0; font-size: 13px;">Latest ${r.message.length} Orders</h6>
						</div>
						<div class="frappe-card">
							<div class="frappe-card-body" style="max-height: 400px; overflow-y: auto; padding: 0;">
								<table class="table table-hover" style="margin: 0; font-size: 13px;">
									<thead style="background: #f8f9fa; position: sticky; top: 0; z-index: 10;">
										<tr style="border-bottom: 1px solid #dee2e6;">
											<th style="${tabledHeadStyle}">Order Number</th>
											<th style="${tabledHeadStyle}">Order Date</th>
											<th style="${tabledHeadStyle}">Financial Status</th>
											<th style="${tabledHeadStyle} text-align: right;">Grand Total</th>
										</tr>
									</thead>
									<tbody>
					`;

					r.message.forEach(function(order) {
						let order_color = order.cancelled_status === 'Cancelled' ? 'rgb(219, 48, 48)' : 'rgb(35, 98, 235)';
						let financial_status_badge = '';

						if (order.financial_status === 'Paid') {
							financial_status_badge = '<span class="indicator-pill green no-indicator-dot filterable">Paid</span>';
						} else if (order.financial_status === 'Partially Paid') {
							financial_status_badge = '<span class="indicator-pill gray no-indicator-dot filterable">Partially Paid</span>';
						} else if (order.financial_status) {
							financial_status_badge = `<span class="indicator-pill blue no-indicator-dot filterable">${order.financial_status}</span>`;
						}

						const display_order_number = order.order_number || order.name;

						html += `
							<tr style="border-bottom: 1px solid #f1f3f4;">
								<td style="${tableDataStyle}">
									<a href="/app/sales-order/${order.name}" style="color: ${order_color}; font-weight: 500; text-decoration: none;">${display_order_number}</a>
								</td>
								<td style="${tableDataStyle} color: #6c757d;">
									${frappe.datetime.str_to_user(order.transaction_date)}
								</td>
								<td style="${tableDataStyle}">
									${financial_status_badge}
								</td>
								<td style="${tableDataStyle} text-align: right; font-weight: 500; color: #495057;">
									${format_currency(order.grand_total, order.currency)}
								</td>
							</tr>
						`;
					});

					html += `
							</tbody>
								</table>
							</div>
							<div class="frappe-card-footer text-left mt-3">
								<a href="/app/sales-order?customer=${encodeURIComponent(frm.doc.name)}" class="btn btn-primary btn-sm">
									${__("View All Orders")}
								</a>
							</div>
						</div>
					`;

					sales_order_wrapper.html(html);
				} else {
					sales_order_wrapper.html(`
						<div class="text-center text-muted" style="padding: 40px;">
							<p style="margin-top: 15px;">No Orders found for this customer.</p>
							<a href="/app/sales-order/new-sales-order?customer=${encodeURIComponent(frm.doc.name)}" class="btn btn-primary btn-sm">
								${__("Create Order")}
							</a>
						</div>
					`);
				}
			},
			error: function(r) {
				sales_order_wrapper.html(`
					<div class="text-center text-danger" style="padding: 20px;">
						<i class="fa fa-exclamation-triangle"></i>
						<p>Error loading Orders. Please check your permissions.</p>
					</div>
				`);
			}
		});
	}
});
