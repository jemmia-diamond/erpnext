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
		let fields = [
			{
				fieldname: "existing_appointment_warning",
				fieldtype: "HTML",
			},

			{
				fieldname: "scheduled_time",
				fieldtype: "Datetime",
				label: __("Scheduled Time"),
				reqd: 1
			},
			{
				fieldname: "at_store",
				fieldtype: "Select",
				label: __("At Store"),
				options: "72 Nguy\u1ec5n C\u01b0 Trinh, Ph\u01b0\u1eddng B\u1ebfn Th\u00e0nh, TP H\u1ed3 Ch\u00ed Minh\n63 Kim M\u00e3, Ph\u01b0\u1eddng Gi\u1ea3ng V\u00f5, TP H\u00e0 N\u1ed9i\n209 \u0110\u01b0\u1eddng 30 Th\u00e1ng 4, Ph\u01b0\u1eddng Ninh Ki\u1ec1u, TP C\u1ea7n Th\u01a1"
			}
		];

		let reason_df = frappe.meta.get_docfield("Appointment", "appointment_reason");
		if (reason_df) fields.push(reason_df);

		return fields;
	}

	setup_custom_logic() {
		frappe.db.get_value("Sales Person", {"employee_email": frappe.session.user}, ["name", "sales_person_name"])
			.then(r => {
				if (r && r.message && r.message.name) {
					if (r.message.sales_person_name) {
						frappe.utils.add_link_title("Sales Person", r.message.name, r.message.sales_person_name);
					}
					this.doc.main_sales = [{
						sales_person: r.message.name
					}];
				}
			});
		this.check_existing_appointment();
	}

	check_existing_appointment() {
		let get_phone_promise = Promise.resolve(this.doc.customer_phone_number);
		if (!this.doc.customer_phone_number) {
			if (this.doc.lead) {
				get_phone_promise = frappe.db.get_value("Lead", this.doc.lead, ["mobile_no", "phone"])
					.then(r => r.message ? (r.message.mobile_no || r.message.phone) : null);
			} else if (this.doc.party && this.doc.appointment_with === "Customer") {
				get_phone_promise = frappe.db.get_value("Customer", this.doc.party, ["mobile_no", "phone"])
					.then(r => r.message ? (r.message.mobile_no || r.message.phone) : null);
			}
		}

		get_phone_promise.then(phone => {
			let or_filters = [];

			if (this.doc.lead) or_filters.push(["lead", "=", this.doc.lead]);
			if (this.doc.party && this.doc.appointment_with === "Customer") or_filters.push(["party", "=", this.doc.party]);
			if (phone) or_filters.push(["customer_phone_number", "=", phone]);

			if (or_filters.length === 0) return;

			frappe.db.get_list("Appointment", {
				filters: [
					["scheduled_time", ">=", frappe.datetime.now_datetime()],
					["status", "=", "Open"]
				],
				or_filters: or_filters,
				fields: ["name", "scheduled_time"]
			}).then(res => {
				if (res && res.length > 0) {
					let appt = res[0];
					let html = `
						<div class="alert alert-warning" style="margin-bottom: 15px;">
							<strong><i class="fa fa-exclamation-triangle"></i> Cảnh báo trùng lặp:</strong> Khách hàng này đã có một lịch hẹn sắp tới vào lúc <b>${appt.scheduled_time}</b>.<br>
							<a href="/app/appointment/${appt.name}" target="_blank" style="text-decoration: underline; font-weight: bold; color: #856404;">
								Bấm vào đây để mở lịch hẹn (${appt.name})
							</a>
						</div>
					`;
					this.dialog.get_field("existing_appointment_warning").$wrapper.html(html);
				}
			});
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
