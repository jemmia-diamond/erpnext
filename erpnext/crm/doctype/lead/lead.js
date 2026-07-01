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

		frappe.dom.set_style(`
			.form-footer { display: none !important; }
			[data-fieldname="all_activities_html"] .form-footer { display: block !important; }
		`, "lead-footer-hide-style");

		$(this.frm.wrapper).on("render_complete.lead_footer", () => {
			$(".form-footer").not("[data-fieldname='all_activities_html'] .form-footer").css("display", "none");
		});
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
			[data-fieldtype="Datetime"] .help-box {
				display: none !important;
			}
		`, "lead-notes-style");

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
								frappe.msgprint(__("Note cannot be empty."));
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
											frappe.msgprint(__("User '{0}' does not exist.", [notify_val]));
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
					frappe.confirm(__("Are you sure you want to delete this note?"), function () {
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
		`, "lead-timeline-style");
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

		frappe.dom.set_style(`
			[data-fieldname="jewelry_interest"] .form-in-grid .grid-move-row,
			[data-fieldname="jewelry_interest"] .form-in-grid .grid-duplicate-row,
			[data-fieldname="jewelry_interest"] .form-in-grid .grid-insert-row,
			[data-fieldname="jewelry_interest"] .form-in-grid .grid-insert-row-below,
			[data-fieldname="jewelry_interest"] .form-in-grid .grid-delete-row,
			
			[data-fieldname="jewelry_interest"] .form-in-grid .grid-footer-toolbar {
				display: none !important;
			}
		`, "lead-jewelry-budget-align");

		frappe.dom.set_style(`
			[data-fieldname="jewelry_interest"] .grid-field > .control-label {
				display: none !important;
			}
			[data-fieldname="jewelry_interest"] .rows > .grid-row .grid-static-col[data-fieldname="product_type"] > .field-area,
			[data-fieldname="jewelry_interest"] .rows > .grid-row .grid-static-col[data-fieldname="product_type"] > .static-area {
				display: none !important;
			}

			[data-fieldname="jewelry_interest"] .frappe-control[data-fieldname="product_type"],
			[data-fieldname="jewelry_interest"] .grid-static-col[data-fieldname="product_type"] {
				overflow: visible !important;
			}
			[data-fieldname="jewelry_interest"] .rows .grid-row {
				overflow: visible !important;
			}
			[data-fieldname="jewelry_interest"] .rows .grid-row > .data-row {
				overflow: visible !important;
			}
			[data-fieldname="jewelry_interest"] .rows {
				overflow: visible !important;
			}
			[data-fieldname="jewelry_interest"] .form-grid {
				overflow: visible !important;
			}
			[data-fieldname="jewelry_interest"] .grid-body {
				overflow: visible !important;
			}
			[data-fieldname="jewelry_interest"] .form-grid-container {
				overflow: visible !important;
			}

			[data-fieldname="jewelry_interest"] .grid-body .rows {
				padding-bottom: 0;
			}
			[data-fieldname="jewelry_interest"] .grid-footer {
				position: relative;
				z-index: 0;
			}

			.tag-suggestions {
				padding: 0 !important;
			}
			.tag-suggestions .tag-sug-item {
				padding: 7px 12px;
				cursor: pointer;
				font-size: 13px;
				font-weight: 500;
				color: var(--text-color, #333);
				border-bottom: 1px solid var(--border-color, #f0f0f0);
				transition: background 0.15s;
			}
			.tag-suggestions .tag-sug-item:last-child {
				border-bottom: none;
			}
			.tag-suggestions .tag-sug-item:hover,
			.tag-suggestions .tag-sug-item.active {
				background: var(--fg-hover-color, #f5f5f5);
			}
			.tag-suggestions .tag-sug-footer {
				padding: 6px 12px;
				cursor: pointer;
				font-size: 12px;
				font-weight: 500;
				color: var(--text-muted, #8d99a6);
				border-top: 1px solid var(--border-color, #d1d8dd);
				display: flex;
				align-items: center;
				gap: 6px;
				transition: background 0.15s;
			}
			.tag-suggestions .tag-sug-footer:hover {
				background: var(--fg-hover-color, #f5f5f5);
			}
			.tag-suggestions .tag-sug-footer .sug-icon {
				font-size: 14px;
				color: var(--primary, #2490ef);
			}

			.custom-tag-widget .tag-input-area {
				display: flex !important;
				flex-wrap: wrap !important;
				gap: 3px !important;
				align-items: center !important;
				border: 1px solid var(--border-color, #d1d8dd) !important;
				border-radius: var(--border-radius, 4px) !important;
				padding: 3px 6px !important;
				min-height: 30px !important;
				background: var(--control-bg, #fff) !important;
				cursor: text !important;
				box-sizing: border-box !important;
			}
			/* Trong grid table: bỏ viền, bỏ nền, fill đầy ô */
			.grid-static-col .custom-tag-widget {
				width: 100% !important;
				height: 100% !important;
				position: relative !important;
			}
			.grid-static-col .custom-tag-widget .tag-input-area {
				border: none !important;
				border-radius: 0 !important;
				background: transparent !important;
				min-height: 100% !important;
				padding: 4px 6px !important;
				width: 100% !important;
			}
			.custom-tag-widget .tag-input {
				border: none !important;
				outline: none !important;
				background: transparent !important;
				flex: 1 !important;
				min-width: 60px !important;
				font-size: var(--text-sm, 12px) !important;
				padding: 1px 2px !important;
				height: 22px !important;
				box-shadow: none !important;
			}
		`, "lead-product-type-overflow");

		// === Setup Product Type grid display ===
		const setup_product_type_grid = () => {
			const grid = frm.fields_dict.jewelry_interest.grid;

			const render_grid_widgets = () => {
				grid.wrapper.find('.grid-row[data-name]').each(function () {
					const cdn = $(this).data('name');
					const $col = $(this).find('.grid-static-col[data-fieldname="product_type"]');
					if (!$col.length) return;

					$col.find('.static-area').hide();
					$col.find('.field-area').hide();

					make_product_type_multiselect(frm, 'Lead Jewelry Interest', cdn, $col, 'grid');
				});
			};

			const orig_refresh = grid.refresh.bind(grid);
			grid.refresh = function () {
				orig_refresh();
				setTimeout(render_grid_widgets, 80);
			};
			render_grid_widgets();

			grid.wrapper.find('.grid-heading-row .grid-static-col[data-fieldname="product_type"]')
				.off('click.pt-block')
				.on('click.pt-block', function (e) {
					e.stopImmediatePropagation();
					e.preventDefault();
				})
				.css('cursor', 'default');
		};
		setup_product_type_grid();

	},
	jewelry_interest_on_form_rendered(frm, cdt, cdn) {
		setTimeout(() => {
			const $form_in_grid = $('[data-fieldname="jewelry_interest"] .form-in-grid:visible');
			if (!$form_in_grid.length) return;

			const $grid_row = $form_in_grid.closest('.grid-row');
			const actual_cdn = $grid_row.data('name');
			const actual_cdt = 'Lead Jewelry Interest';
			if (!actual_cdn) return;

			$form_in_grid.find('.grid-move-row, .grid-duplicate-row, .grid-insert-row, .grid-insert-row-below, .grid-delete-row')
				.each(function () { this.style.setProperty('display', 'none', 'important'); });
			$form_in_grid.find('.grid-footer-toolbar')
				.each(function () { this.style.setProperty('display', 'none', 'important'); });

			$form_in_grid.find('[data-fieldname="diamond_detail"]').closest('.frappe-control').hide();

			const $pt = $form_in_grid.find('[data-fieldname="product_type"]');
			if ($pt.length) {
				$pt.find('.control-input').hide();
				$pt.find('.control-value').hide();
				const $target = $pt.find('.control-input-wrapper');
				if ($target.length) {
					make_product_type_multiselect(frm, actual_cdt, actual_cdn, $target, 'form');
				}
			}
		}, 150);
	},

});
frappe.ui.form.on("Lead Jewelry Interest", {
	size: function (frm, cdt, cdn) {
		update_diamond_detail(frm, cdt, cdn);
	},
	shape: function (frm, cdt, cdn) {
		update_diamond_detail(frm, cdt, cdn);
	},
	color_grade: function (frm, cdt, cdn) {
		update_diamond_detail(frm, cdt, cdn);
	},
	clarity_grade: function (frm, cdt, cdn) {
		update_diamond_detail(frm, cdt, cdn);
	}
});
function update_diamond_detail(frm, cdt, cdn) {
	let child = locals[cdt][cdn];
	let parts = [];

	if (child.size) {
		parts.push(child.size);
	}
	if (child.shape) {
		parts.push(child.shape);
	}
	if (child.color_grade) {
		parts.push(child.color_grade);
	}
	if (child.clarity_grade) {
		parts.push(child.clarity_grade);
	}

	let detail = parts.join(" - ");
	frappe.model.set_value(cdt, cdn, "diamond_detail", detail);
}

if (!window._pt_widget_registry) {
	window._pt_widget_registry = {};
}

function _pt_get_vals(cdn) {
	const row = locals['Lead Jewelry Interest'] && locals['Lead Jewelry Interest'][cdn];
	if (!row) return [];
	return (row.product_type || "").split(",").map(s => s.trim()).filter(Boolean);
}

function _pt_render_tags($widget, vals) {
	const $container = $widget.find(".tags-container");
	$container.empty();
	vals.forEach(v => {
		const $tag = $('<span class="pt-tag"></span>').text(v).css({
			display: 'inline-flex', alignItems: 'center', gap: '3px',
			background: 'var(--fg-color,#f0f0f0)',
			border: '1px solid var(--border-color,#d1d8dd)',
			borderRadius: 'var(--border-radius,4px)',
			padding: '1px 6px', fontSize: '11px', lineHeight: '20px', whiteSpace: 'nowrap'
		});
		const $remove = $('<span class="tag-remove">&times;</span>').css({
			cursor: 'pointer', color: 'var(--text-muted,#8d99a6)',
			fontSize: '13px', fontWeight: 'bold', marginLeft: '2px'
		});
		$remove.data('tag-value', v);
		$tag.append($remove);
		$container.append($tag);
	});
}

function _pt_sync_all(frm, cdn, new_val_str) {
	const row = locals['Lead Jewelry Interest'] && locals['Lead Jewelry Interest'][cdn];
	if (row) {
		row.product_type = new_val_str;
	}
	frm.dirty();

	const grid = frm.fields_dict.jewelry_interest && frm.fields_dict.jewelry_interest.grid;
	if (grid) {
		const $row = grid.wrapper.find(`.grid-row[data-name="${cdn}"]`);
		if ($row.length) {
			$row.find('input[data-fieldname="product_type"]').val(new_val_str);
		}
	}

	const vals = (new_val_str || "").split(",").map(s => s.trim()).filter(Boolean);
	const widgets = window._pt_widget_registry[cdn] || [];
	widgets.forEach(entry => {
		if (entry.$widget && entry.$widget.closest('body').length) {
			_pt_render_tags(entry.$widget, vals);
		}
	});

	window._pt_widget_registry[cdn] = widgets.filter(
		entry => entry.$widget && entry.$widget.closest('body').length
	);
}

function make_product_type_multiselect(frm, cdt, cdn, $wrapper, context) {
	$wrapper.find('.custom-tag-widget').remove();

	if (!window._pt_widget_registry[cdn]) {
		window._pt_widget_registry[cdn] = [];
	}
	window._pt_widget_registry[cdn] = window._pt_widget_registry[cdn].filter(
		entry => entry.$widget && entry.$widget.closest('body').length
	);

	const vals = _pt_get_vals(cdn);

	const $widget = $(`
		<div class="custom-tag-widget" data-cdn="${cdn}" data-context="${context}" style="position:relative; width:100%;">
			<div class="tag-input-area" style="
				display:flex;flex-wrap:wrap;gap:3px;align-items:center;
				border:1px solid var(--border-color,#d1d8dd);
				border-radius:var(--border-radius,4px);
				padding:3px 6px;min-height:30px;
				background:var(--control-bg,#fff);cursor:text;
			">
				<div class="tags-container" style="display:contents"></div>
				<input class="tag-input" placeholder="" autocomplete="off" style="
					border:none;outline:none;background:transparent;
					flex:1;min-width:60px;font-size:var(--text-sm,12px);
					padding:1px 2px;height:22px;
				"/>
			</div>
			<div class="tag-suggestions" style="
				display:none;position:absolute;z-index:99999;width:100%;
				background:#fff;border:1px solid var(--border-color,#d1d8dd);
				border-radius:var(--border-radius,4px);margin-top:2px;
				box-shadow:0 4px 12px rgba(0,0,0,0.1);
				max-height:180px;overflow-y:auto;left:0;top:100%;
			"></div>
		</div>
	`);
	$wrapper.append($widget);

	_pt_render_tags($widget, vals);

	window._pt_widget_registry[cdn].push({ $widget, context });

	$widget.find(".tag-input-area").on("click", (e) => {
		if ($(e.target).closest('.tag-remove').length) return; // cho phép bubble lên delegation handler
		e.stopPropagation();
		$widget.find(".tag-input").focus();
	});

	$widget.on("click", ".tag-remove", function (e) {
		e.stopPropagation();
		e.preventDefault();
		const remove_val = $(this).data('tag-value');
		if (!remove_val) return;
		let current = _pt_get_vals(cdn);
		current = current.filter(v => v !== remove_val);
		_pt_sync_all(frm, cdn, current.join(", "));
	});

	const addTag = (val) => {
		val = (val || "").trim();
		if (!val) return;
		let current = _pt_get_vals(cdn);
		if (!current.includes(val)) {
			current.push(val);
			_pt_sync_all(frm, cdn, current.join(", "));

			// Auto-create Lead Product Type nếu chưa tồn tại
			frappe.db.get_list("Lead Product Type", {
				filters: [["product_type", "=", val]],
				fields: ["name"], limit: 1
			}).then(results => {
				if (!results.length) {
					frappe.db.insert({ doctype: "Lead Product Type", product_type: val });
				}
			});
		}
		$widget.find(".tag-input").val("");
		$widget.find(".tag-suggestions").hide();
	};

	$widget.find(".tag-input").on("keydown", e => {
		if (e.key === "Enter") { e.preventDefault(); addTag($(e.target).val()); }
	});

	const showSuggestions = (q) => {
		const $sug = $widget.find(".tag-suggestions");
		const currentVals = _pt_get_vals(cdn);
		const filters = q ? [["product_type", "like", `%${q}%`]] : [];
		frappe.db.get_list("Lead Product Type", {
			filters, fields: ["name", "product_type"], limit: 20
		}).then(results => {
			$sug.empty();
			const filtered = results.filter(r => !currentVals.includes(r.product_type));
			filtered.forEach(r => {
				const $item = $('<div class="tag-sug-item"></div>')
					.text(r.product_type)
					.data('sug-value', r.product_type);
				$sug.append($item);
			});

			const create_label = q
				? `Tạo mới "${frappe.utils.escape_html(q)}"`
				: 'Tạo mới Lead Product Type';
			const $create = $('<div class="tag-sug-footer tag-sug-create"></div>')
				.html(`<span class="sug-icon">+</span> ${create_label}`);
			if (q) {
				$create.data('sug-value', q);
			}
			$sug.append($create);

			$sug.show();
		});
	};

	$widget.find(".tag-input").on("focus", function () {
		$('.custom-tag-widget .tag-suggestions').not($widget.find('.tag-suggestions')).hide();
		showSuggestions($(this).val().trim());
	});
	$widget.find(".tag-input").on("input", function () { showSuggestions($(this).val().trim()); });

	$widget.on("click", ".tag-sug-item", function (e) {
		e.stopPropagation();
		addTag($(this).data('sug-value'));
		$widget.find(".tag-input").val("").focus();
	});

	$widget.on("click", ".tag-sug-create", function (e) {
		e.stopPropagation();
		const val = $(this).data('sug-value');
		if (val) {
			addTag(val);
			$widget.find(".tag-input").val("").focus();
		} else {
			const d = new frappe.ui.Dialog({
				title: __('New Lead Product Type'),
				fields: [{ label: 'Product Type', fieldname: 'product_type', fieldtype: 'Data', reqd: 1 }],
				primary_action_label: __('Create'),
				primary_action(values) {
					if (values.product_type) {
						addTag(values.product_type.trim());
					}
					d.hide();
				}
			});
			d.show();
			$widget.find(".tag-suggestions").hide();
		}
	});

	const close_handler = `click.tag-widget-${cdn}-${context}`;
	$(document).off(close_handler).on(close_handler, e => {
		if (!$(e.target).closest($widget).length) {
			$widget.find(".tag-suggestions").hide();
		}
	});
}


