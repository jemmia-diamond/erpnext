frappe.provide("frappe.ui.form");

frappe.ui.form.LeadQuickEntryForm = class LeadQuickEntryForm extends frappe.ui.form.QuickEntryForm {
	render_dialog() {
		// Inject search phone field at the top of quick entry
		this.docfields = [
			{
				fieldname: "search_phone",
				fieldtype: "Data",
				label: __("Search Phone"),
			},
			{
				fieldtype: "HTML",
				fieldname: "phone_search_results",
			},
			{
				fieldtype: "Section Break",
			},
			...this.docfields,
		];

		super.render_dialog();
		this._setup_phone_search();
	}

	_setup_phone_search() {
		let me = this;
		let timer = null;
		let $input = this.fields_dict.search_phone.$input;
		let $results = $(this.fields_dict.phone_search_results.wrapper);

		// Style the results container for awesomplete-like dropdown
		$results.css("position", "relative");

		$input.on("input", function () {
			clearTimeout(timer);
			let val = $(this).val().trim();
			if (val.length < 3) {
				$results.empty();
				return;
			}
			timer = setTimeout(() => {
				frappe.call({
					method: "erpnext.crm.doctype.lead.lead.search_leads_by_phone",
					args: { phone: val },
					callback(r) {
						$results.empty();

						if (!r.message || !r.message.length) {
							$results.html(
								`<p style="color:var(--text-muted);font-size:var(--text-sm);padding:6px 0;margin:0;">
									${__("Không tìm thấy lead nào.")}
								</p>`
							);
							return;
						}

						let $list = $(`<ul class="list-unstyled lead-phone-results"></ul>`);
						$list.css({
							background: "var(--fg-color)",
							border: "1px solid var(--border-color)",
							borderRadius: "var(--border-radius-lg)",
							boxShadow: "var(--shadow-sm)",
							maxHeight: "220px",
							overflowY: "auto",
							margin: "2px 0 0",
							padding: "0",
						});

						r.message.forEach((lead) => {
							let display_name = lead.lead_name || lead.first_name || lead.name;
							let phone_display = lead.phone || lead.mobile_no || "";

							let $li = $(`<li class="lead-search-item" data-name="${lead.name}"></li>`);
							$li.css({
								padding: "9px 12px",
								cursor: "pointer",
								borderBottom: "1px solid var(--border-color)",
							});

							$li.html(`
								<div style="display:flex;justify-content:space-between;align-items:center;">
									<div style="min-width:0;flex:1;">
										<div style="font-weight:600;font-size:var(--text-md);color:var(--text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
											${frappe.utils.escape_html(display_name)}
											<span style="font-weight:400;color:var(--text-muted);margin-left:6px;">${frappe.utils.escape_html(phone_display)}</span>
										</div>
										<div style="font-size:var(--text-sm);color:var(--text-light);margin-top:2px;">
											${frappe.utils.escape_html(lead.name)}
										</div>
									</div>
									
								</div>
							`);

							$li.on("mouseenter", function () {
								$(this).css("background", "var(--fg-hover-color)");
							}).on("mouseleave", function () {
								$(this).css("background", "");
							});

							$li.on("click", function () {
								window.open(`/app/lead/${encodeURIComponent($(this).data("name"))}`, "_blank");
							});

							$list.append($li);
						});

						// Remove border from last item
						$list.find("li:last-child").css("borderBottom", "none");

						$results.append($list);
					},
				});
			}, 400);
		});
	}

	_get_status_color(status) {
		const map = {
			Lead: "orange",
			Open: "orange",
			Replied: "blue",
			Opportunity: "yellow",
			Quotation: "blue",
			"Lost Quotation": "gray",
			Interested: "blue",
			Converted: "green",
			"Do Not Contact": "red",
			Lost: "red",
		};
		return map[status] || "gray";
	}

	insert() {
		// Copy search_phone value to phone field if phone is empty
		let search_val = this.dialog.get_value("search_phone");
		if (search_val && !this.dialog.doc.phone) {
			this.dialog.doc.phone = search_val.trim();
		}
		return super.insert();
	}
};
