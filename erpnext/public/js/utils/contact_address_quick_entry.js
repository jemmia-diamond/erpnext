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
		this.setup_save_validation();
	}

	setup_save_validation() {
		const me = this;
		this.dialog.set_primary_action(__("Save"), function() {
			const mobile_no = me.dialog.get_value('mobile_number');
			if (!mobile_no || !mobile_no.trim()) {
				frappe.msgprint(__("Mobile number is required"));
				return;
			}
			me.dialog.set_primary_action(__("Checking"), null);
			me.dialog.get_primary_btn().prop('disabled', true);
			me.validate_mobile_number(mobile_no.trim()).then(() => {
				me.proceed_with_save();
			}).catch(() => {
				me.reset_save_button();
			});
		});
	}

	reset_save_button() {
		const me = this;
		this.dialog.set_primary_action(__("Save"), function() {
			const mobile_no = me.dialog.get_value('mobile_number');
			if (!mobile_no || !mobile_no.trim()) {
				frappe.msgprint(__("Mobile number is required"));
				return;
			}
			me.dialog.set_primary_action(__("Checking"), null);
			me.dialog.get_primary_btn().prop('disabled', true);
			me.validate_mobile_number(mobile_no.trim()).then(() => {
				me.proceed_with_save();
			}).catch(() => {
				me.reset_save_button();
			});
		});
		this.dialog.get_primary_btn().prop('disabled', false);
	}

	proceed_with_save() {
		this.insert();
	}

	insert() {
		/**
		 * Using alias fieldnames because the doctype definition define "email_id" and "mobile_no" as readonly fields.
		 * This results in the fields being "hidden".
		 */
		const map_field_names = {
			email_address: "email_id",
			mobile_number: "mobile_no",
			// map_to_first_name: "first_name",
			// map_to_last_name: "last_name",
			// country_address: "country",
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
			// {
			// 	label: __("First Name"),
			// 	fieldname: "map_to_first_name",
			// 	fieldtype: "Data",
			// 	depends_on: "eval:doc.customer_type=='Company' || doc.supplier_type=='Company'",
			// },
			// {
			// 	label: __("Last Name"),
			// 	fieldname: "map_to_last_name",
			// 	fieldtype: "Data",
			// 	depends_on: "eval:doc.customer_type=='Company' || doc.supplier_type=='Company'",
			// },
			{
				fieldtype: "Column Break",
			},
			{
				label: __("Email Id"),
				fieldname: "email_address",
				fieldtype: "Data",
				options: "Email",
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
				// mandatory_depends_on: "eval:doc.city || doc.country_address",
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
				// mandatory_depends_on: "eval:doc.country_address || doc.address_line1",
			},
			{
				label: __("State/Province"),
				fieldname: "state",
				fieldtype: "Data",
			},
			{
				label: __("Country"),
				fieldname: "country_address",
				fieldtype: "Link",
				options: "Country",
				// mandatory_depends_on: "eval:doc.city || doc.address_line1",
			},
		];

		return variant_fields;
	}
};
