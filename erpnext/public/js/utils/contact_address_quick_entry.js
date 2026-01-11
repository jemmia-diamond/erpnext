frappe.provide("frappe.ui.form");

frappe.ui.form.ContactAddressQuickEntryForm = class ContactAddressQuickEntryForm extends (
	frappe.ui.form.QuickEntryForm
) {
	constructor(doctype, after_insert, init_callback, doc, force) {
		super(doctype, after_insert, init_callback, doc, force);
		this.skip_redirect_on_error = true;
	}

	render_dialog() {
		this.mandatory = this.mandatory.concat(this.get_variant_fields());
		super.render_dialog();
		this.setup_mobile_validation();
	}

	setup_mobile_validation() {
		const me = this;
		this.dialog.get_primary_btn().prop('disabled', true);		
		if (!this.dialog.fields_dict.mobile_number) {
			return;
		}

		const check_btn = $(`
			<button class="btn btn-sm btn-secondary check-mobile-btn" style="margin-top: 5px;">
				${__("Check")}
			</button>
		`);
		
		this.dialog.fields_dict.mobile_number.$wrapper.append(check_btn);
		this.dialog.fields_dict.mobile_number.$input.on('input', function() {
			const mobile_value = $(this).val().trim();
			const check_btn = me.dialog.fields_dict.mobile_number.$wrapper.find('.check-mobile-btn');
			
			if (!mobile_value) {
				me.dialog.get_primary_btn().prop('disabled', true);
				check_btn.hide();
			} else {
				me.dialog.get_primary_btn().prop('disabled', true);
				check_btn.show().text(__("Check")).prop('disabled', false);
			}
		});

		check_btn.on('click', function() {
			const mobile_no = me.dialog.get_value('mobile_number');
			if (!mobile_no || !mobile_no.trim()) {
				frappe.msgprint(__("Please enter a mobile number first"));
				return;
			}

			const trimmed_mobile = mobile_no.trim();			
			$(this).text(__("Checking")).prop('disabled', true);

			me.validate_mobile_number(trimmed_mobile).then(() => {
				me.dialog.get_primary_btn().prop('disabled', false);
				$(this).hide();
				frappe.show_alert({
					message: __("Phone number available"),
					indicator: "green"
				});
			}).catch(() => {
				$(this).text(__("Check")).prop('disabled', false);
			});
		});
	}

	insert() {
		/**
		 * Using alias fieldnames because the doctype definition define "email_id" and "mobile_no" as readonly fields.
		 * Therefor, resulting in the fields being "hidden".
		 */
		const map_field_names = {
			email_address: "email_id",
			mobile_number: "mobile_no",
			gender: "gender"
		};

		Object.entries(map_field_names).forEach(([fieldname, new_fieldname]) => {
			this.dialog.doc[new_fieldname] = this.dialog.doc[fieldname];
			delete this.dialog.doc[fieldname];
		});

		return super.insert();
	}

	validate_mobile_number(mobile_no) {
		return new Promise((resolve, reject) => {
			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "Customer",
					or_filters: [
						["mobile_no", "=", mobile_no],
						["phone", "=", mobile_no]
					],
					fields: ["name", "customer_name"]
				},
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						const existing_customer = r.message[0];
						frappe.msgprint({
							title: __("Duplicate Mobile Number"),
							message: __("Mobile number {0} already exists for customer: {1}", 
								[mobile_no, existing_customer.customer_name || existing_customer.name]),
							indicator: "orange"
						});
						reject();
					} else {
						resolve();
					}
				},
				error: function() {
					reject();
				}
			});
		});
	}

	get_variant_fields() {
		var variant_fields = [
			{
				fieldtype: "Section Break",
				label: __("Primary Contact Details"),
			},
			{
				label: __("Email Id"),
				fieldname: "email_address",
				fieldtype: "Data",
				options: "Email",
			},
			{
				fieldtype: "Column Break",
			},
			{
				label: __("Mobile Number"),
				fieldname: "mobile_number",
				fieldtype: "Data",
				reqd: 1
			},
			{
				label: __("Gender"),
				fieldname: "gender",
				fieldtype: "Link",
				options: "Gender"
			},
			{
				fieldtype: "Section Break",
				label: __("Primary Address Details"),
				collapsible: 1,
				hidden: 1
			},
			{
				label: __("Address Line 1"),
				fieldname: "address_line1",
				fieldtype: "Data",
			},
			{
				label: __("Address Line 2"),
				fieldname: "address_line2",
				fieldtype: "Data",
			},
			{
				label: __("ZIP Code"),
				fieldname: "pincode",
				fieldtype: "Data",
			},
			{
				fieldtype: "Column Break",
			},
			{
				label: __("City"),
				fieldname: "city",
				fieldtype: "Data",
			},
			{
				label: __("State"),
				fieldname: "state",
				fieldtype: "Data",
			},
			{
				label: __("Country"),
				fieldname: "country",
				fieldtype: "Link",
				options: "Country",
			},
			{
				label: __("Customer POS Id"),
				fieldname: "customer_pos_id",
				fieldtype: "Data",
				hidden: 1,
			},
		];

		return variant_fields;
	}
};
