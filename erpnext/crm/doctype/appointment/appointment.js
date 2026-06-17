// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Appointment", {
	refresh: function (frm) {
		if (frm.doc.lead) {
			frm.add_custom_button(__("View Lead"), () => {
				frappe.set_route("Form", "Lead", frm.doc.lead);
			});
		}
		if (frm.doc.calendar_event) {
			frm.add_custom_button(__(frm.doc.calendar_event), () => {
				frappe.set_route("Form", "Event", frm.doc.calendar_event);
			});
		}
	},

	onload: function (frm) {
		// Restrict "Appointment With" to Customer or Lead only
		frm.set_query("appointment_with", function () {
			return {
				filters: {
					name: ["in", ["Customer", "Lead"]],
				},
			};
		});

		// Restrict the Lead link field to search by phone number if phone is filled
		frm.set_query("lead", function () {
			if (frm.doc.customer_phone_number) {
				return {
					filters: {
						mobile_no: frm.doc.customer_phone_number,
					},
				};
			}
			return {};
		});
	},

	// When the user types a phone number, auto-search for a matching Lead
	customer_phone_number: function (frm) {
		const phone = frm.doc.customer_phone_number;
		if (!phone) return;

		frappe.db.get_list("Lead", {
			filters: { mobile_no: phone },
			fields: ["name", "first_name", "lead_name", "annual_revenue"],
			limit: 1,
		}).then((leads) => {
			if (leads && leads.length > 0) {
				const lead = leads[0];
				frm.set_value("lead", lead.name);

				// Auto-fill Name from Lead's first_name (Lead Name)
				if (!frm.doc.customer_name && lead.first_name) {
					frm.set_value("customer_name", lead.first_name);
				}

				// Auto-fill Estimated Budget from Lead's annual_revenue (Lead Budget)
				if (!frm.doc.estimated_budget && lead.annual_revenue) {
					frm.set_value("estimated_budget", lead.annual_revenue);
				}

				frappe.show_alert({
					message: __("Lead found and linked: {0}", [lead.name]),
					indicator: "green",
				});
			}
		});
	},

	// When a Lead is manually selected, fetch and fill data from it
	lead: function (frm) {
		const lead_name = frm.doc.lead;
		if (!lead_name) return;

		frappe.db.get_doc("Lead", lead_name).then((lead) => {
			// Fill "Name" from Lead Name (first_name field)
			if (lead.first_name) {
				frm.set_value("customer_name", lead.first_name);
			}

			// Fill "Estimated Budget" from Lead annual_revenue (Lead Budget)
			if (lead.proposed_budget) {
				frm.set_value("estimated_budget", String(lead.proposed_budget));
			}

			// Fill "Budget Range" from custom field if it exists (Propose Lead Budget)
			if (lead.budget_lead) {
				frm.set_value("range_estimated_budget", lead.budget_lead);
			}

			// Fill email if not already set
			if (!frm.doc.customer_email) {
				frm.set_value("customer_email", lead.email_id);
			}

			// Fill phone
			if (lead.phone) {
				frm.set_value("customer_phone_number", lead.phone);
			}
		});
	},
});
