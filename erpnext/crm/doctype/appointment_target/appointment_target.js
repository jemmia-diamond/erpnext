// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Appointment Target", {
	refresh(frm) {
		// Custom UI logic if needed
	},
});

// frappe.ui.form.on("Appointment Target Item", {
// 	targets_add(frm, cdt, cdn) {
// 		let total_rows = (frm.doc.targets || []).length;
// 		frappe.model.set_value(cdt, cdn, "target_name", `Tier ${total_rows}`);
// 	},
// });
