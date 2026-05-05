// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bank Transaction", {
	setup: function (frm) {
		frm.set_query("party_type", function () {
			return {
				filters: {
					name: ["in", Object.keys(frappe.boot.party_account_types)],
				},
			};
		});

		frm.set_query("bank_account", function () {
			return {
				filters: { is_company_account: 1 },
			};
		});

		frm.set_query("payment_document", "payment_entries", function () {
			const payment_doctypes = frm.events.get_payment_doctypes(frm);
			return {
				filters: {
					name: ["in", payment_doctypes],
				},
			};
		});

		frm.set_query("payment_entry", "payment_entries", function () {
			return {
				filters: {
					docstatus: ["!=", 2],
				},
			};
		});
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			let can_cancel = true;

			if (frm.doc.payment_entries && frm.doc.payment_entries.length > 0) {
				if (!frappe.user.has_role("Administrator")
					&& !frappe.user.has_role("Developer")
					&& !frappe.user.has_role("Accounts User")
					&& !frappe.user.has_role("Accounts Manager")) {
					can_cancel = false;
				}
			}

			if (can_cancel) {
				frm.add_custom_button(__("Cancel"), function () {
					frappe.confirm(
						__("Bạn có chắc chắn muốn huỷ Giao dịch ngân hàng này không?"),
						function () {
							frappe.call({
								method: "cancel_transaction",
								doc: frm.doc,
								callback: function (r) {
									if (!r.exc) {
										frappe.show_alert({
											message: __("Huỷ Giao dịch ngân hàng thành công"),
											indicator: "green"
										});
										frm.reload_doc();
									}
								}
							});
						}
					);
				}).addClass("btn-danger");
			}
		}

		if (!frm.is_dirty() && frm.doc.payment_entries.length > 0) {
			frm.add_custom_button(__("Unreconcile Transaction"), () => {
				frm.call("remove_payment_entries").then(() => frm.refresh());
			});
		}
	},

	bank_account: function (frm) {
		set_bank_statement_filter(frm);
	},

	get_payment_doctypes: function () {
		// get payment doctypes from all the apps
		return ["Payment Entry", "Journal Entry", "Sales Invoice", "Purchase Invoice", "Bank Transaction"];
	},
});

function set_bank_statement_filter(frm) {
	frm.set_query("bank_statement", function () {
		return {
			filters: {
				bank_account: frm.doc.bank_account,
			},
		};
	});
}
