// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
frappe.provide("erpnext");
frappe.ui.form.on('SMS Template', {
	refresh(frm) {
		
        frappe.call({
            method: 'erpnext.crm.doctype.sms_template.sms_template.get_branches',
            callback: function(r) {
                if (r.message) {
                    // Assuming r.message is a list of strings like ['Branch A', 'Branch B']
                    let options = r.message.join('\n');
                    frm.set_df_property('branch_name', 'options', options);
                    frm.refresh_field('branch_name');  // Important to refresh field after change
                }
            }
        });
	}
})

