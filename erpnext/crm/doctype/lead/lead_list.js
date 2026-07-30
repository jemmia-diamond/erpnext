const VISIBLE_PHONE_DIGITS = 5;

frappe.listview_settings["Lead"] = {
	hide_name_column: true,
	get_indicator: function (doc) {
		const colors = {
			"Lead": "blue",
			"New": "blue",
			"Prospecting": "orange",
			"Nurturing": "purple",
			"Qualified": "green",
			"Converted": "darkgreen",
			"Do Not Contact": "gray",
			"Spam": "red"
		};
		const color = colors[doc.status] || "gray";
		return [__(doc.status), color, "status,=," + doc.status];
	},
	onload: function (listview) {
		const CONVERTIBLE_OPERATORS = ['like', 'not like', '=', '!='];

		const original_get_args = listview.get_args.bind(listview);
		listview.get_args = function() {
			const args = original_get_args();

			if (args.filters) {
				const newFilters = [];
				const phoneOrFilters = [];

				args.filters.forEach(filter => {
					if (Array.isArray(filter) && filter[1] === 'phone' && CONVERTIBLE_OPERATORS.includes(filter[2]) && filter[3]) {
						let phone = filter[3].replace(/%/g, '').trim();
						phone = phone.replace(/[\s\-\(\)]/g, '');

						const operator = filter[2];
						const useWildcards = operator.includes('like');
						const phoneValue = useWildcards ? '%' + phone + '%' : phone;
						const phone84Value = useWildcards ? '%84' + phone.substring(1) + '%' : '84' + phone.substring(1);

						if (phone.startsWith('0') && phone.length >= 4) {
							phoneOrFilters.push(['Lead', 'phone', operator, phoneValue]);
							phoneOrFilters.push(['Lead', 'phone', operator, phone84Value]);
						} else {
							phoneOrFilters.push(['Lead', 'phone', operator, phoneValue]);
						}
					} else {
						newFilters.push(filter);
					}
				});
				args.filters = newFilters;
				if (phoneOrFilters.length > 0) {
					args.or_filters = phoneOrFilters;
				}
			}

			return args;
		};

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
	},
};

function maskPhoneNumber(phone, visibleDigits) {
	const maskedPart = '*'.repeat(phone.length - visibleDigits);
	const visiblePart = phone.slice(-visibleDigits);
	return maskedPart + visiblePart;
}
