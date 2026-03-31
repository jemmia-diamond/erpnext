const VISIBLE_PHONE_DIGITS = 5;

frappe.listview_settings["Lead"] = {
	hide_name_column: true,
	get_indicator: function (doc) {
		var indicator = [__(doc.status), frappe.utils.guess_colour(doc.status), "status,=," + doc.status];
		return indicator;
	},
	onload: function (listview) {
		if (frappe.boot.user.can_create.includes("Prospect")) {
			listview.page.add_action_item(__("Create Prospect"), function () {
				frappe.model.with_doctype("Prospect", function () {
					let prospect = frappe.model.get_new_doc("Prospect");
					let leads = listview.get_checked_items();
					frappe.db.get_value(
						"Lead",
						leads[0].name,
						[
							"company_name",
							"no_of_employees",
							"industry",
							"market_segment",
							"territory",
							"fax",
							"website",
							"lead_owner",
						],
						(r) => {
							prospect.company_name = r.company_name;
							prospect.no_of_employees = r.no_of_employees;
							prospect.industry = r.industry;
							prospect.market_segment = r.market_segment;
							prospect.territory = r.territory;
							prospect.fax = r.fax;
							prospect.website = r.website;
							prospect.prospect_owner = r.lead_owner;

							leads.forEach(function (lead) {
								let lead_prospect_row = frappe.model.add_child(prospect, "leads");
								lead_prospect_row.lead = lead.name;
							});
							frappe.set_route("Form", "Prospect", prospect.name);
						}
					);
				});
			});
		}
	},

	refresh: function (listview) {
		$(".list-row-container .list-row .level-right .comment-count").remove();
		$(".list-row-container .list-row .level-right .mx-2").remove();
		$(".list-row-container .list-row .level-right .list-row-like").remove();

		// Mask phone numbers in list view
		const phoneCells = $('.list-row-container [data-filter^="phone,="]');
		phoneCells.each(function () {
			const phoneCell = $(this);
			const phone = phoneCell.text().trim();
			if (phone && phone.length > VISIBLE_PHONE_DIGITS) {
				phoneCell.text(maskPhoneNumber(phone, VISIBLE_PHONE_DIGITS));
			}
		});

		for (let i = 0; i < listview.data.length; i++) {
			const row = $(`.result .list-row-container:nth-child(${i + 3}) .list-row`);
			const doc = listview.data[i];

			// Add Avatar
			var avatar = "";
			const select = row.find(".list-subject .select-like");
			if(doc.image) {
				avatar = `
				<span class="avatar avatar-small level-item filterable" title="${doc.first_name}" style="margin-right: 4px; padding: 3px;">
     				<span class="avatar-frame" style="background-image: url(&quot;${doc.image}&quot;)" title="${doc.first_name}"></span>
				</span>
				`
			} else {
				avatar = `
				<span class="avatar avatar-small level-item filterable" title="${doc.first_name}" style="margin-right: 4px; padding: 3px;">
					<div class="avatar-frame standard-image" style="background-color: var(--red-avatar-bg); color: var(--red-avatar-color)" title="${doc.first_name}">${doc.first_name.charAt(0).toUpperCase()}</div>
				</span>
				`
			}
			select.after($(avatar));

			// Add Pancake button
			const activity = row.find(".level-right .list-row-activity");
			frappe.db.get_list("Contact", {
				filters: [
					["Dynamic Link", "link_doctype", "=", "Lead"],
					["Dynamic Link", "link_name", "=", doc.name],
					["pancake_conversation_id", "!=", null]
				],
				fields: ["name", "pancake_conversation_id", "pancake_page_id"]
			}).then((contacts) => {
				if (contacts.length) {
					const contact = contacts[0];
					if (contact.pancake_conversation_id && contact.pancake_page_id) {
						var btn = $('<button class="btn btn-primary btn-pancake">P</button>');
						btn.on('click', function (e) {
							e.stopPropagation();
							window.open(`https://pancake.vn/${contact.pancake_page_id}?c_id=` + contact.pancake_conversation_id, '_blank');
						});
						activity.append(btn);
					}
				}
			});
		}
	},
};

function maskPhoneNumber(phone, visibleDigits) {
	const maskedPart = '*'.repeat(phone.length - visibleDigits);
	const visiblePart = phone.slice(-visibleDigits);
	return maskedPart + visiblePart;
}
