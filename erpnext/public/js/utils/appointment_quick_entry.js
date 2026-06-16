frappe.provide("frappe.ui.form");

frappe.ui.form.AppointmentQuickEntryForm = class AppointmentQuickEntryForm extends frappe.ui.form.QuickEntryForm {
	constructor(doctype, after_insert, init_callback, doc, force) {
		super(doctype, after_insert, init_callback, doc, force);
	}

	render_dialog() {
		this.docfields = this.get_custom_fields();
		super.render_dialog();
		this.setup_custom_logic();
	}

	get_custom_fields() {
		return [
			{
				fieldname: "scheduled_time",
				fieldtype: "Datetime",
				label: __("Scheduled Time"),
				reqd: 1
			},
			{
				fieldname: "status",
				fieldtype: "Select",
				label: "Status",
				options: "Kh\u00e1ch \u0111\u00e3 mua h\u00e0ng\nKh\u00e1ch h\u1eb9n \u0111\u1ebfn c\u1eeda h\u00e0ng\nKh\u00e1ch ch\u01b0a mua h\u00e0ng\nKh\u00e1ch kh\u00f4ng \u0111\u1ebfn c\u1eeda h\u00e0ng\nKh\u00e1ch ho\u00e3n l\u1ea1i ng\u00e0y \u0111\u1ebfn c\u1eeda h\u00e0ng\nKh\u00e1ch \u0111\u00e3 \u0111\u1ebfn c\u1eeda h\u00e0ng",
				reqd: 1
			},
			{
				fieldname: "store",
				fieldtype: "Select",
				label: __("Store"),
				options: "72 NCT\n63 KM\nCần Thơ"
			},
			{
				fieldname: "gender",
				fieldtype: "Link",
				label: __("Gender"),
				options: "Gender",
				read_only: 1
			},
			{
				fieldname: "customer_name",
				fieldtype: "Data",
				label: __("Customer Name"),
				reqd: 1
			},
			{
				fieldname: "customer_phone_number",
				fieldtype: "Data",
				label: __("Phone Number")
			},
			{
				fieldname: "main_sales",
				fieldtype: "Table MultiSelect",
				label: __("Main Sales Person"),
				options: "Appointment Sales Person"
			},
			{
				fieldname: "offline_sales",
				fieldtype: "Table MultiSelect",
				label: "Offline Sales Person",
				options: "Appointment Sales Person"
			},
			{
				fieldname: "conversation_greeting",
				fieldtype: "Small Text",
				label: __("In-Store Greeting Content")
			},
			{
				fieldname: "notes",
				fieldtype: "Small Text",
				label: __("Notes")
			}
		];
	}

	setup_custom_logic() {
		this.dialog.set_df_property("customer_phone_number", "read_only", 0);

		if (this.doc.party) {
			this.dialog.set_df_property("gender", "hidden", 1);
		}

		if (this.doc.customer_phone_number) {
			this.dialog.set_df_property("customer_phone_number", "read_only", 1);
		}

		// Fetch Sales Person name for current user email and set as main_sales
		frappe.db.get_value("Sales Person", {"employee_email": frappe.session.user}, ["name", "sales_person_name"])
			.then(r => {
				if (r && r.message && r.message.name) {
					if (r.message.sales_person_name) {
						frappe.utils.add_link_title("Sales Person", r.message.name, r.message.sales_person_name);
					}
					this.dialog.set_value('main_sales', [{
						sales_person: r.message.name
					}]);
				}
			});
	}

	insert() {
		return new Promise((resolve, reject) => {
			let scheduled_time = this.dialog.get_value("scheduled_time");
			if (scheduled_time && scheduled_time < frappe.datetime.now_datetime()) {
				frappe.msgprint({
					title: __("Validation Error"),
					indicator: "red",
					message: __("Scheduled Time cannot be in the past.")
				});
				this.dialog.working = false;
				return reject("Validation failed");
			}
			super.insert().then(resolve).catch(reject);
		});
	}

};
