// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt
frappe.provide("erpnext.crm");
erpnext.pre_sales.set_as_lost("Opportunity");
erpnext.sales_common.setup_selling_controller();

frappe.ui.form.on("Opportunity", {
	setup: function (frm) {
		frm.custom_make_buttons = {
			Quotation: "Quotation",
			"Supplier Quotation": "Supplier Quotation",
		};

		frm.set_query("opportunity_from", function () {
			return {
				filters: {
					name: ["in", ["Customer", "Lead", "Prospect"]],
				},
			};
		});

		frm.email_field = "contact_email";
	},

	validate: function (frm) {
		if (frm.doc.status == "Lost" && !frm.doc.lost_reasons.length) {
			frm.trigger("set_as_lost_dialog");
			frappe.throw(__("Lost Reasons are required in case opportunity is Lost."));
		}
	},

	onload_post_render: function (frm) {
		frm.get_field("items").grid.set_multiple_add("item_code", "qty");
	},

	party_name: function (frm) {
		frm.trigger("set_contact_link");

		if (frm.doc.opportunity_from == "Customer") {
			erpnext.utils.get_party_details(frm);
		} else if (frm.doc.opportunity_from == "Lead") {
			erpnext.utils.map_current_doc({
				method: "erpnext.crm.doctype.lead.lead.make_opportunity",
				source_name: frm.doc.party_name,
				frm: frm,
			});
		}
	},

	status: function (frm) {
		if (frm.doc.status == "Lost") {
			frm.trigger("set_as_lost_dialog");
		}
	},

	customer_address: function (frm, cdt, cdn) {
		erpnext.utils.get_address_display(frm, "customer_address", "address_display", false);
	},

	contact_person: erpnext.utils.get_contact_details,

	opportunity_from: function (frm) {
		frm.trigger("setup_opportunity_from");

		frm.set_value("party_name", "");
	},

	setup_opportunity_from: function (frm) {
		frm.trigger("setup_queries");
		frm.trigger("set_dynamic_field_label");
	},

	refresh: function (frm) {
		var doc = frm.doc;
		frm.trigger("setup_opportunity_from");
		erpnext.toggle_naming_series();

		if (!frm.is_new() && doc.status !== "Lost") {
			if (doc.items) {
				frm.add_custom_button(
					__("Supplier Quotation"),
					function () {
						frm.trigger("make_supplier_quotation");
					},
					__("Create")
				);

				frm.add_custom_button(
					__("Request For Quotation"),
					function () {
						frm.trigger("make_request_for_quotation");
					},
					__("Create")
				);
			}

			if (frm.doc.opportunity_from != "Customer") {
				frm.add_custom_button(
					__("Customer"),
					function () {
						frm.trigger("make_customer");
					},
					__("Create")
				);
			}

			frm.add_custom_button(
				__("Quotation"),
				function () {
					frm.trigger("create_quotation");
				},
				__("Create")
			);

			let company_currency = erpnext.get_currency(frm.doc.company);
			if (company_currency != frm.doc.currency) {
				frm.add_custom_button(__("Fetch Latest Exchange Rate"), function () {
					frm.trigger("currency");
				});
			}
		}

		if (!frm.doc.__islocal && frm.perm[0].write && frm.doc.docstatus == 0) {
			if (frm.doc.status === "Open") {
				frm.add_custom_button(__("Close"), function () {
					frm.set_value("status", "Closed");
					frm.save();
				});
			} else {
				frm.add_custom_button(__("Reopen"), function () {
					frm.set_value("lost_reasons", []);
					frm.set_value("status", "Open");
					frm.save();
				});
			}
		}

		if (!frm.is_new()) {
			frappe.contacts.render_address_and_contact(frm);
			// frm.trigger('render_contact_day_html');
		} else {
			frappe.contacts.clear_address_and_contact(frm);
		}

		if (frm.doc.opportunity_from && frm.doc.party_name) {
			frm.trigger("set_contact_link");
		}

		if (frm.doc && frm.doc.name && !frm.doc.__islocal) {
			render_custom_comments(frm);
		} else {
			let html_notice = `
				<div style="text-align: center; color: #8c99a6; padding: 30px; background-color: #fff; border-radius: 8px;">
					<i class="fa fa-info-circle" style="font-size: 24px; margin-bottom: 10px; color: #ffb100;"></i>
					<p style="margin: 0; font-size: 13px;">Vui lòng bấm nút <b>Save (Lưu)</b> Cơ hội này trước để kích hoạt tính năng Bình luận.</p>
				</div>
			`;
			if (frm.fields_dict['custom_comment_list']) {
				frm.fields_dict['custom_comment_list'].$wrapper.html(html_notice);
			}
		}
	},

	set_contact_link: function (frm) {
		if (frm.doc.opportunity_from == "Customer" && frm.doc.party_name) {
			frappe.dynamic_link = { doc: frm.doc, fieldname: "party_name", doctype: "Customer" };
		} else if (frm.doc.opportunity_from == "Lead" && frm.doc.party_name) {
			frappe.dynamic_link = { doc: frm.doc, fieldname: "party_name", doctype: "Lead" };
		} else if (frm.doc.opportunity_from == "Prospect" && frm.doc.party_name) {
			frappe.dynamic_link = { doc: frm.doc, fieldname: "party_name", doctype: "Prospect" };
		}
	},

	currency: function (frm) {
		let company_currency = erpnext.get_currency(frm.doc.company);
		if (company_currency != frm.doc.currency) {
			frappe.call({
				method: "erpnext.setup.utils.get_exchange_rate",
				args: {
					from_currency: frm.doc.currency,
					to_currency: company_currency,
				},
				callback: function (r) {
					if (r.message) {
						frm.set_value("conversion_rate", flt(r.message));
						frm.set_df_property(
							"conversion_rate",
							"description",
							"1 " + frm.doc.currency + " = [?] " + company_currency
						);
					}
				},
			});
		} else {
			frm.set_value("conversion_rate", 1.0);
			frm.set_df_property("conversion_rate", "hidden", 1);
			frm.set_df_property("conversion_rate", "description", "");
		}

		frm.trigger("opportunity_amount");
		frm.trigger("set_dynamic_field_label");
	},

	opportunity_amount: function (frm) {
		frm.set_value(
			"base_opportunity_amount",
			flt(frm.doc.opportunity_amount) * flt(frm.doc.conversion_rate)
		);
	},

	set_dynamic_field_label: function (frm) {
		if (frm.doc.opportunity_from) {
			frm.set_df_property("party_name", "label", frm.doc.opportunity_from);
		}
		frm.trigger("change_grid_labels");
		frm.trigger("change_form_labels");
	},

	make_supplier_quotation: function (frm) {
		frappe.model.open_mapped_doc({
			method: "erpnext.crm.doctype.opportunity.opportunity.make_supplier_quotation",
			frm: frm,
		});
	},

	make_request_for_quotation: function (frm) {
		frappe.model.open_mapped_doc({
			method: "erpnext.crm.doctype.opportunity.opportunity.make_request_for_quotation",
			frm: frm,
		});
	},

	change_form_labels: function (frm) {
		let company_currency = erpnext.get_currency(frm.doc.company);
		frm.set_currency_labels(["base_opportunity_amount", "base_total"], company_currency);
		frm.set_currency_labels(["opportunity_amount", "total"], frm.doc.currency);

		// toggle fields
		frm.toggle_display(
			["conversion_rate", "base_opportunity_amount", "base_total"],
			frm.doc.currency != company_currency
		);
	},

	change_grid_labels: function (frm) {
		let company_currency = erpnext.get_currency(frm.doc.company);
		frm.set_currency_labels(["base_rate", "base_amount"], company_currency, "items");
		frm.set_currency_labels(["rate", "amount"], frm.doc.currency, "items");

		let item_grid = frm.fields_dict.items.grid;
		$.each(["base_rate", "base_amount"], function (i, fname) {
			if (frappe.meta.get_docfield(item_grid.doctype, fname))
				item_grid.set_column_disp(fname, frm.doc.currency != company_currency);
		});
		frm.refresh_fields();
	},

	calculate_total: function (frm) {
		let total = 0,
			base_total = 0;
		frm.doc.items.forEach((item) => {
			total += item.amount;
			base_total += item.base_amount;
		});

		frm.set_value({
			total: flt(total),
			base_total: flt(base_total),
		});
	},
});
frappe.ui.form.on("Opportunity Item", {
	calculate: function (frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
		frappe.model.set_value(cdt, cdn, "base_rate", flt(frm.doc.conversion_rate) * flt(row.rate));
		frappe.model.set_value(cdt, cdn, "base_amount", flt(frm.doc.conversion_rate) * flt(row.amount));
		frm.trigger("calculate_total");
	},
	qty: function (frm, cdt, cdn) {
		frm.trigger("calculate", cdt, cdn);
	},
	rate: function (frm, cdt, cdn) {
		frm.trigger("calculate", cdt, cdn);
	},
});

// TODO commonify this code
erpnext.crm.Opportunity = class Opportunity extends frappe.ui.form.Controller {
	onload() {
		if (!this.frm.doc.status) {
			this.frm.set_value("status", "Open");
		}
		if (!this.frm.doc.company && frappe.defaults.get_user_default("Company")) {
			this.frm.set_value("company", frappe.defaults.get_user_default("Company"));
		}
		if (!this.frm.doc.currency) {
			this.frm.set_value("currency", frappe.defaults.get_user_default("Currency"));
		}

		if (this.frm.is_new() && this.frm.doc.opportunity_type === undefined) {
			this.frm.doc.opportunity_type = __("Sales");
		}
		this.setup_queries();
	}

	refresh() {
		this.show_notes();
		this.show_activities();
	}

	setup_queries() {
		var me = this;

		me.frm.set_query("customer_address", erpnext.queries.address_query);

		this.frm.set_query("item_code", "items", function () {
			return {
				query: "erpnext.controllers.queries.item_query",
				filters: { is_sales_item: 1 },
			};
		});

		this.frm.set_query("uom", "items", function (doc, cdt, cdn) {
			let row = locals[cdt][cdn];

			if (!row.item_code) {
				return;
			}

			return {
				query: "erpnext.controllers.queries.get_item_uom_query",
				filters: {
					item_code: row.item_code,
				},
			};
		});

		me.frm.set_query("contact_person", erpnext.queries["contact_query"]);

		if (me.frm.doc.opportunity_from == "Lead") {
			me.frm.set_query("party_name", erpnext.queries["lead"]);
		} else if (me.frm.doc.opportunity_from == "Customer") {
			me.frm.set_query("party_name", erpnext.queries["customer"]);
		} else if (me.frm.doc.opportunity_from == "Prospect") {
			me.frm.set_query("party_name", function () {
				return {
					filters: {
						company: me.frm.doc.company,
					},
				};
			});
		}
	}

	create_quotation() {
		frappe.model.open_mapped_doc({
			method: "erpnext.crm.doctype.opportunity.opportunity.make_quotation",
			frm: this.frm,
		});
	}

	make_customer() {
		frappe.model.open_mapped_doc({
			method: "erpnext.crm.doctype.opportunity.opportunity.make_customer",
			frm: this.frm,
		});
	}

	show_notes() {
		const crm_notes = new erpnext.utils.CRMNotes({
			frm: this.frm,
			notes_wrapper: $(this.frm.fields_dict.notes_html.wrapper),
		});
		crm_notes.refresh();
	}

	show_activities() {
		const crm_activities = new erpnext.utils.CRMActivities({
			frm: this.frm,
			open_activities_wrapper: $(this.frm.fields_dict.open_activities_html.wrapper),
			all_activities_wrapper: $(this.frm.fields_dict.all_activities_html.wrapper),
			form_wrapper: $(this.frm.wrapper),
		});
		crm_activities.refresh();
	}
};

extend_cscript(cur_frm.cscript, new erpnext.crm.Opportunity({ frm: cur_frm }));

cur_frm.cscript.item_code = function (doc, cdt, cdn) {
	var d = locals[cdt][cdn];
	if (d.item_code) {
		return frappe.call({
			method: "erpnext.crm.doctype.opportunity.opportunity.get_item_details",
			args: { item_code: d.item_code },
			callback: function (r, rt) {
				if (r.message) {
					$.each(r.message, function (k, v) {
						frappe.model.set_value(cdt, cdn, k, v);
					});
					refresh_field("image_view", d.name, "items");
				}
			},
		});
	}
};
function render_custom_comments(frm) {
	frappe.call({
		method: 'frappe.client.get_list',
		args: {
			doctype: 'Comment',
			fields: ['name', 'comment_by', 'content', 'creation', 'owner'],
			filters: {
				reference_doctype: frm.doc.doctype,
				reference_name: frm.doc.name,
				comment_type: 'Comment'
			},
			order_by: 'creation desc',
			limit: 100
		},
		callback: function(r) {
			let comments = r.message || [];

			let html_content = `
				<div class="frappe-custom-comments-wrapper" style="padding: 10px 0; font-family: inherit;">
					<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
						<div style="font-size: 16px; font-weight: 600; color: var(--text-color);">${__('Comments')} (${comments.length})</div>
						<button class="btn btn-primary btn-sm button-style" id="btn-custom-new-comment" style="display: inline-flex; align-items: center; gap: 6px;">
							<svg class="icon icon-sm" style="stroke: #fff; fill: none;"><use href="#icon-add"></use></svg>
							<span>${__('New Comment')}</span>
						</button>
					</div>
					
					<div id="custom-comments-container" style="max-height: 600px; overflow-y: auto; padding-left: 8px;">
			`;

			if (comments.length === 0) {
				html_content += `
					<div style="text-align: center; color: var(--text-muted); padding: 40px 20px; border: 1px dashed var(--border-color); border-radius: 8px;">
						<p style="margin: 0; font-size: 13px;">${__('No comments yet. Start the conversation!')}</p>
					</div>
				`;
			} else {
				comments.forEach((comment, index) => {
					// Format thời gian sang dạng DD-MM-YYYY HH:MM chuẩn Việt Nam
					let time_display = '';
					if (comment.creation) {
						let dt = comment.creation.split(' ');
						let date_part = dt[0].split('-').reverse().join('-');
						let time_part = dt[1].split('.')[0].substring(0, 5);
						time_display = `${time_part} ${date_part}`;
					}
					let sender_name = comment.comment_by || comment.owner || 'User';
					
					// Đổ CSS Flat chuẩn của các block element trong Frappe Form Timeline
					html_content += `
						<div class="custom-comment-item" style="display: flex; align-items: flex-start; margin-bottom: 20px; position: relative;">
							
							${index !== comments.length - 1 ? `<div style="position: absolute; left: 16px; top: 32px; bottom: -28px; width: 1px; background-color: var(--border-color);"></div>` : ''}

							<div style="width: 32px; height: 32px; background-color: var(--gray-100); border: 1px solid var(--border-color); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 500; color: var(--text-color); margin-right: 16px; flex-shrink: 0; font-size: 12px; text-transform: uppercase;">
								${sender_name.charAt(0)}
							</div>
							
							<div style="flex-grow: 1; padding-top: 2px;">
								<div style="display: flex; align-items: baseline; gap: 8px; margin-bottom: 4px;">
									<span style="font-weight: 600; color: var(--text-color); font-size: 13px;">${sender_name}</span>
									<span style="font-size: 11px; color: var(--text-muted); font-weight: normal;">• ${time_display}</span>
								</div>
								<div style="color: var(--text-color); font-size: 13px; line-height: 1.6; word-break: break-word; white-space: pre-line;">
									${comment.content}
								</div>
							</div>
						</div>
					`;
				});
			}

			html_content += `</div></div>`;

			if (frm.fields_dict['custom_comment_list'] && frm.fields_dict['custom_comment_list'].$wrapper) {
				frm.fields_dict['custom_comment_list'].$wrapper.html(html_content);
			}

			// Xử lý sự kiện click nút thêm mới bình luận
			$('#btn-custom-new-comment').off('click').on('click', function() {
				let d = new frappe.ui.Dialog({
					title: __('Add Comment'),
					fields: [
						{
							label: __('Comment'),
							fieldname: 'comment_text',
							fieldtype: 'Small Text',
							reqd: 1
						}
					],
					primary_action_label: __('Submit'),
					primary_action(values) {
						d.get_primary_btn().attr('disabled', true).html(__('Saving...'));
						frappe.call({
							method: 'frappe.client.insert',
							args: {
								doc: {
									doctype: 'Comment',
									comment_type: 'Comment',
									reference_doctype: frm.doc.doctype,
									reference_name: frm.doc.name,
									content: values.comment_text,
									comment_by: frappe.session.user_fullname || frappe.session.user
								}
							},
							callback: function(res) {
								d.hide();
								frappe.show_alert({message: __('Comment posted'), indicators: 'green'});
								frm.reload_doc().then(() => {
									render_custom_comments(frm);
								});
							},
							error: function() {
								d.get_primary_btn().attr('disabled', false).html(__('Submit'));
							}
						});
					}
				});
				d.show();
			});
		}
	});
}