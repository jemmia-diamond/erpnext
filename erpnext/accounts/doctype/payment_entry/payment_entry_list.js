frappe.listview_settings["Payment Entry"] = {
	hide_name_column: true,
	onload: function (listview) {
		if (listview.page.fields_dict.party_type) {
			listview.page.fields_dict.party_type.get_query = function () {
				return {
					filters: {
						name: ["in", Object.keys(frappe.boot.party_account_types)],
					},
				};
			};
		}

		let phone_timeout;
		let order_timeout;
		let custom_phone_search = null;
		let custom_order_search = null;
		let custom_reference_filter = "";

		const original_get_args = listview.get_args.bind(listview);
		listview.get_args = function() {
			const args = original_get_args();

			if (custom_phone_search) {
				args.phone_search = custom_phone_search;
			}
			if (custom_order_search) {
				args.order_number_search = custom_order_search;
			}
			if (custom_reference_filter) {
				args.reference_filter = custom_reference_filter;
			}

			return args;
		};

		const original_get_call_args = listview.get_call_args.bind(listview);
		listview.get_call_args = function(args) {
			const call_args = original_get_call_args(args);
			if (custom_phone_search || custom_order_search || custom_reference_filter) {
				call_args.method = "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry_list";
				call_args.phone_search = custom_phone_search;
				call_args.order_number_search = custom_order_search;
				call_args.reference_filter = custom_reference_filter;
			}
			return call_args;
		};

		const $filter_area = listview.page.page_form.find('.standard-filter-section');
		if ($filter_area.length) {
			const $phone_wrapper = $('<div class="form-group frappe-control input-max-width col-md-2"></div>');
			const $phone_input = $('<input type="text" autocomplete="off" class="input-with-feedback form-control input-xs" placeholder="' + __('Phone') + '">');
			$phone_input.on('input', function() {
				const phone = $(this).val();
				clearTimeout(phone_timeout);
				phone_timeout = setTimeout(() => {
					custom_phone_search = phone || null;
					listview.refresh();
				}, 500);
			});
			$phone_wrapper.append($phone_input);

			const $order_wrapper = $('<div class="form-group frappe-control input-max-width col-md-2"></div>');
			const $order_input = $('<input type="text" autocomplete="off" class="input-with-feedback form-control input-xs" placeholder="' + __('Order Number') + '">');
			$order_input.on('input', function() {
				const order_number = $(this).val();
				clearTimeout(order_timeout);

				order_timeout = setTimeout(() => {
					custom_order_search = order_number || null;
					listview.refresh();
				}, 500);
			});

			$order_wrapper.append($order_input);

			const $reference_wrapper = $('<div class="form-group frappe-control input-max-width col-md-2"></div>');
			const $reference_select = $('<select class="input-with-feedback form-control input-xs">' +
				'<option value="" selected disabled hidden>' + __('Order link status') + '</option>' +
				'<option value="">' + __('All') + '</option>' +
				'<option value="has_references">' + __('Order linked') + '</option>' +
				'<option value="no_references">' + __('Not linked') + '</option>' +
				'</select>');
			$reference_select.on('change', function() {
				custom_reference_filter = $(this).val();
				listview.refresh();
			});
			$reference_wrapper.append($reference_select);

			const $my_entries_wrapper = $('<div class="form-group frappe-control input-max-width col-md-2"></div>');
			const $my_entries_checkbox = $('<label class="checkbox" style="margin-top: 8px;">' +
				'<input type="checkbox" class="input-with-feedback"> ' +
				'<span class="label-area">' + __('My Payment Entries') + '</span>' +
				'</label>');
			$my_entries_checkbox.find('input[type="checkbox"]').on('change', function() {
				if ($(this).is(':checked')) {
					listview.filter_area.add([["Payment Entry", "created_by_display", "=", frappe.session.user]]);
				} else {
					listview.filter_area.remove("created_by_display");
				}
			});
			$my_entries_wrapper.append($my_entries_checkbox);

			$filter_area.append($my_entries_wrapper).append($phone_wrapper).append($order_wrapper).append($reference_wrapper);

			const $total_wrapper = $('<div class="form-group frappe-control input-max-width col-md-2" style="margin-top: 8px; font-weight: bold; color: var(--text-color);"></div>');
			const $total_label = $('<span>' + __('Total Paid: ') + '</span><span id="total-paid-amount">0</span>');
			$total_wrapper.append($total_label);
			$filter_area.append($total_wrapper);

			const original_refresh = listview.refresh.bind(listview);
			listview.refresh = function() {
				original_refresh();
				frappe.call({
					method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry_list_total",
					args: listview.get_args(),
					callback: function(r) {
						if (r.message != null) {
							$('#total-paid-amount').text(format_currency(r.message));
						}
					}
				});
			};
		}
	},
};
