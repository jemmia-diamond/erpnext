// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("erpnext");
if (this.frm) {
	this.frm.email_field = "email_id";
}
erpnext.LeadController = class LeadController extends frappe.ui.form.Controller {
	setup() {
		this.frm.make_methods = {
			Customer: this.make_customer.bind(this),
			Quotation: this.make_quotation.bind(this),
			Opportunity: this.make_opportunity.bind(this),
		};

		// For avoiding integration issues.
		this.frm.set_df_property("first_name", "reqd", true);
	}

	onload() {
		this.frm.set_query("lead_owner", function (doc, cdt, cdn) {
			return { query: "frappe.core.doctype.user.user.user_query" };
		});
	}

	refresh() {
		var me = this;
		let doc = this.frm.doc;
		erpnext.toggle_naming_series();

		if (!this.frm.is_new() && doc.__onload && !doc.__onload.is_customer) {
			this.frm.add_custom_button(__("Customer"), this.make_customer.bind(this), __("Create"));
			this.frm.add_custom_button(__("Opportunity"), this.make_opportunity.bind(this), __("Create"));
		}

		if (!this.frm.is_new()) {
			this.frm.add_custom_button(__("Appointment"), this.make_appointment.bind(this), __("Create"));
		}

		if (!this.frm.is_new()) {
			frappe.contacts.render_address_and_contact(this.frm);
		} else {
			frappe.contacts.clear_address_and_contact(this.frm);
		}

		this.frm.set_df_property('notes', 'hidden', 1);

		frappe.dom.set_style(`
			/* Notes card layout */
			.notes-section .all-notes {
				border: 1px solid #e5e7eb;
				border-radius: 8px;
				overflow: hidden;
				margin-top: 4px;
			}
			.comment-content {
				position: relative;
				padding: 14px 100px 14px 16px !important;
				border: none !important;
				border-bottom: 1px solid #f3f4f6 !important;
				margin: 0 !important;
				background: #fff !important;
				box-shadow: none !important;
				border-radius: 0 !important;
				display: block !important;
			}
			.comment-content:last-child {
				border-bottom: none !important;
			}
			.comment-content .head {
				display: none !important;
			}
			.comment-content .content {
				width: 100% !important;
				padding: 0 !important;
				float: none !important;
			}
			.comment-content > .col-xs-1.text-right {
				position: absolute !important;
				top: 10px !important;
				right: 10px !important;
				width: auto !important;
				float: none !important;
				z-index: 10 !important;
				display: flex !important;
				flex-direction: column !important;
				gap: 2px !important;
			}
			.comment-content > .col-xs-1.text-right .btn-link {
				pointer-events: all !important;
				cursor: pointer !important;
				padding: 2px 4px !important;
				line-height: 1 !important;
			}
			.note-text {
				font-size: 14px !important;
				font-weight: 500 !important;
				color: #111827 !important;
				line-height: 1.6 !important;
				word-break: break-word !important;
			}
			.note-meta {
				font-size: 11px;
				color: #9ca3af;
				margin-top: 6px;
			}
			.note-notify {
				display: inline-flex;
				align-items: center;
				gap: 3px;
				background: #eff6ff;
				color: #2563eb;
				border-radius: 999px;
				padding: 1px 8px;
				font-size: 11px;
				font-weight: 500;
			}
		`);


		this.show_notes();
		this.show_activities();
	}

	add_lead_to_prospect(frm) {
		frappe.prompt(
			[
				{
					fieldname: "prospect",
					label: __("Prospect"),
					fieldtype: "Link",
					options: "Prospect",
					reqd: 1,
				},
			],
			function (data) {
				frappe.call({
					method: "erpnext.crm.doctype.lead.lead.add_lead_to_prospect",
					args: {
						lead: frm.doc.name,
						prospect: data.prospect,
					},
					callback: function (r) {
						if (!r.exc) {
							frm.reload_doc();
						}
					},
					freeze: true,
					freeze_message: __("Adding Lead to Prospect..."),
				});
			},
			__("Add Lead to Prospect"),
			__("Add")
		);
	}

	make_customer() {
		frappe.model.open_mapped_doc({
			method: "erpnext.crm.doctype.lead.lead.make_customer",
			frm: this.frm,
		});
	}

	make_quotation() {
		frappe.model.open_mapped_doc({
			method: "erpnext.crm.doctype.lead.lead.make_quotation",
			frm: this.frm,
		});
	}

	async make_opportunity() {
		const frm = this.frm;
		let existing_prospect = (
			await frappe.db.get_value(
				"Prospect Lead",
				{
					lead: frm.doc.name,
				},
				"name",
				null,
				"Prospect"
			)
		).message?.name;

		let fields = [];

		await frm.reload_doc();

		let existing_contact = (
			await frappe.db.get_value(
				"Contact",
				{
					first_name: frm.doc.first_name || frm.doc.lead_name,
					last_name: frm.doc.last_name,
				},
				"name"
			)
		).message?.name;

		if (!existing_contact) {
			fields.push({
				label: "Create Contact",
				fieldname: "create_contact",
				fieldtype: "Check",
				default: "1",
			});
		}

		if (fields.length) {
			const d = new frappe.ui.Dialog({
				title: __("Create Opportunity"),
				fields: fields,
				primary_action: function (data) {
					frappe.call({
						method: "create_prospect_and_contact",
						doc: frm.doc,
						args: {
							data: data,
						},
						freeze: true,
						callback: function (r) {
							if (!r.exc) {
								frappe.model.open_mapped_doc({
									method: "erpnext.crm.doctype.lead.lead.make_opportunity",
									frm: frm,
								});
							}
							d.hide();
						},
					});
				},
				primary_action_label: __("Create"),
			});
			d.show();
		} else {
			frappe.model.open_mapped_doc({
				method: "erpnext.crm.doctype.lead.lead.make_opportunity",
				frm: frm,
			});
		}
	}

	make_prospect() {
		const me = this;
		frappe.model.with_doctype("Prospect", function () {
			let prospect = frappe.model.get_new_doc("Prospect");
			prospect.company_name = me.frm.doc.company_name;
			prospect.no_of_employees = me.frm.doc.no_of_employees;
			prospect.industry = me.frm.doc.industry;
			prospect.market_segment = me.frm.doc.market_segment;
			prospect.territory = me.frm.doc.territory;
			prospect.fax = me.frm.doc.fax;
			prospect.website = me.frm.doc.website;
			prospect.prospect_owner = me.frm.doc.lead_owner;
			prospect.notes = me.frm.doc.notes;

			let leads_row = frappe.model.add_child(prospect, "leads");
			leads_row.lead = me.frm.doc.name;

			frappe.set_route("Form", "Prospect", prospect.name);
		});
	}

	make_appointment() {
		const frm = this.frm;
		frappe.new_doc("Appointment", {
			lead: frm.doc.name,
			appointment_with: "Lead",
			customer_name: frm.doc.lead_name,
			customer_phone_number: frm.doc.phone,
			customer_email: frm.doc.email_id,
			estimated_budget: frm.doc.proposed_budget || undefined,
			range_estimated_budget: frm.doc.budget_lead || undefined,
			gender: frm.doc.gender || undefined,
		});
	}

	company_name() {
		if (!this.frm.doc.lead_name) {
			this.frm.set_value("lead_name", this.frm.doc.company_name);
		}
	}

	show_notes() {
		if (this.frm.doc.docstatus == 1) return;
		if (this.frm.is_new()) return;

		const frm = this.frm;
		const $wrapper = $(frm.fields_dict.notes_html.wrapper);

		const get_all_notes = () => new Promise((resolve) => {
			frappe.call({
				method: "erpnext.crm.doctype.lead.lead.get_related_notes",
				args: { doctype: frm.doc.doctype, docname: frm.doc.name },
				callback: (r) => resolve(r.message || [])
			});
		});

		const render_notes = () => {
			$wrapper.find(".notes-section").remove();

			get_all_notes().then(notes => {
				notes.sort((a, b) => new Date(b.added_on) - new Date(a.added_on));

				notes.forEach(n => {
					let raw = n.note || "";
					let cleaned = raw;
					if (raw.includes('custom-note-card')) {
						let m = raw.match(/<div class="note-text">([\s\S]*?)<\/div>/);
						cleaned = m ? m[1] : raw;
					}

					n._raw_note = cleaned;

					let tag = "";
					const is_foreign = (n.parent !== frm.doc.name || n.parenttype !== frm.doc.doctype);
					if (is_foreign) {
						let path = n.parenttype.toLowerCase();
						let bg = "#f3f4f6";
						let clr = "#374151";
						if (n.parenttype === "Lead") {
							bg = "#fef9c3"; clr = "#92400e";
						} else if (n.parenttype === "Opportunity") {
							bg = "#dbeafe"; clr = "#1e40af";
						} else if (n.parenttype === "Appointment") {
							bg = "#e0f2fe"; clr = "#0369a1";
						}
						tag = `<a href="/app/${path}/${encodeURIComponent(n.parent)}"
							style="display:inline-block;padding:2px 10px;border-radius:999px;
							       font-size:11px;font-weight:600;background:${bg};color:${clr};
							       text-decoration:none;margin-bottom:8px;"
							onclick="event.stopPropagation();">${__(n.parenttype)}: ${n.parent}</a>`;
					}

					let by = n.added_by || "";
					let dt = n.added_on ? frappe.datetime.global_date_format(n.added_on) : "";
					let notify = n.notify_to_name
						? `<span class="note-notify">→ ${frappe.utils.escape_html(n.notify_to_name)}</span>`
						: "";
					let meta = by
						? `<div class="note-meta">${by}${dt ? " · " + dt : ""}${notify ? " · " + notify : ""}</div>`
						: "";

					n.note = `<div class="custom-note-card">${tag}<div class="note-text">${cleaned}</div>${meta}</div>`;
					n._is_foreign = is_foreign;
				});

				let html = frappe.render_template("crm_notes", { notes });
				$(html).appendTo($wrapper);

				$wrapper.find(".new-note-btn").off("click").on("click", () => {
					let d = new frappe.ui.Dialog({
						title: __("Add a Note"),
						fields: [
							{ label: "Note", fieldname: "note", fieldtype: "Text Editor", reqd: 1, enable_mentions: true },
							{ label: "Notify To", fieldname: "notify_to", fieldtype: "Link", options: "User" }
						],
						primary_action_label: __("Add"),
						primary_action(vals) {
							frappe.call({
								method: "add_note",
								doc: frm.doc,
								args: { note: vals.note, notify_to: vals.notify_to },
								freeze: true,
								callback(r) {
									if (!r.exc) { frm.refresh_field("notes"); render_notes(); d.hide(); }
								}
							});
						}
					});
					d.show();
				});

				notes.forEach(n => {
					if (n._is_foreign) {
						$wrapper.find(`[name="${n.name}"] .edit-note-btn`).remove();
						$wrapper.find(`[name="${n.name}"] .delete-note-btn`).remove();
					} else {
						let $card = $wrapper.find(`[name="${n.name}"]`);
						$card.data('note_content', n._raw_note || "");
						$card.data('notify_to', n.notify_to || "");

						if (n.added_by !== frappe.session.user) {
							$card.find(".delete-note-btn").remove();
							$card.find(".edit-note-btn").remove();
						}
					}
				});

				$wrapper.find(".edit-note-btn").off("click").on("click", function () {
					let $card = $(this).closest(".comment-content");
					let row_name = $card.attr("name");
					let note_content = $card.data("note_content") || "";
					let notify_to = $card.data("notify_to") || "";

					let d = new frappe.ui.Dialog({
						title: __("Edit Note"),
						fields: [
							{ label: "Note", fieldname: "note", fieldtype: "Text Editor", reqd: 1 },
							{ label: "Notify To", fieldname: "notify_to", fieldtype: "Link", options: "User", default: notify_to }
						],
						primary_action_label: __("Done"),
						primary_action(vals) {
							const note_val = vals.note || "";
							const notify_val = vals.notify_to || null;

							if (!note_val.trim()) {
								frappe.msgprint(__("Ghi chú không được để trống."));
								return;
							}

							const do_save = () => {
								frappe.call({
									method: "edit_note",
									doc: frm.doc,
									args: { note: note_val, notify_to: notify_val, row_id: row_name },
									freeze: true,
									callback(r) {
										if (!r.exc) { frm.refresh_field("notes"); render_notes(); d.hide(); }
									}
								});
							};

							// Validate notify_to nếu có giá trị
							if (notify_val) {
								frappe.db.get_value("User", notify_val, "name")
									.then(r => {
										if (r.message && r.message.name) {
											do_save();
										} else {
											frappe.msgprint(__("Người dùng '{0}' không tồn tại.", [notify_val]));
										}
									});
							} else {
								do_save();
							}
						}
					});
					d.show();
					if (note_content) d.set_value("note", note_content);
				});

				$wrapper.find(".delete-note-btn").off("click").on("click", function () {
					let row_name = $(this).closest(".comment-content").attr("name");
					frappe.confirm(__("Xác nhận xóa ghi chú này?"), function () {
						frappe.call({
							method: "delete_note",
							doc: frm.doc,
							args: { row_id: row_name },
							freeze: true,
							callback(r) {
								if (!r.exc) { frm.refresh_field("notes"); render_notes(); }
							}
						});
					});
				});
			});
		};

		render_notes();
	}






	show_activities() {
		if (this.frm.doc.docstatus == 1) return;

		const crm_activities = new erpnext.utils.CRMActivities({
			frm: this.frm,
			open_activities_wrapper: $(this.frm.fields_dict.open_activities_html.wrapper),
			all_activities_wrapper: $(this.frm.fields_dict.all_activities_html.wrapper),
			form_wrapper: $(this.frm.wrapper),
		});
		crm_activities.refresh();
	}
};

if (cur_frm) {
	extend_cscript(cur_frm.cscript, new erpnext.LeadController({ frm: cur_frm }));
}

frappe.ui.form.on('Lead', {
	refresh(frm) {
		frappe.dom.set_style(`
			.new-task-btn, .new-event-btn, .timeline-actions {
				display: none !important;
			}
		`);
		if (!frm.is_quick_entry) {
			frm.set_df_property('custom_note', 'hidden', 1);
		}
		// Check Contact associated with this Lead
		frappe.db.get_list("Contact", {
			filters: [
				["Dynamic Link", "link_doctype", "=", "Lead"],
				["Dynamic Link", "link_name", "=", frm.doc.name]
			],
			fields: ["name", "pancake_conversation_id", "pancake_page_id", "source"]
		}).then(data => {
			data.forEach(contact => {
				if (contact.pancake_conversation_id && contact.pancake_page_id) {
					if (contact.source) {
						frappe.db.get_doc("Lead Source", contact.source).then(source => {
							frm.add_web_link(`https://pancake.vn/${contact.pancake_page_id}?c_id=` + contact.pancake_conversation_id, `${source.source_name}`);
						})
					} else {
						frm.add_web_link(`https://pancake.vn/${contact.pancake_page_id}?c_id=` + contact.pancake_conversation_id, `Pancake Conversation`);
					}
				}
			})
		});
	}
})
