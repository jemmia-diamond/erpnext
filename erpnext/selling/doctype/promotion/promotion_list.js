frappe.listview_settings['Promotion'] = {
	onload: function(listview) {
		listview.page.add_inner_button(__('Sync Diamond Collect'), frappe.utils.debounce(() => {
			const btn_label = __('Sync Diamond Collect');
			const $btn = listview.page.get_inner_button(btn_label);

			$btn.prop("disabled", true);
			frappe.dom.freeze(__('Syncing...'));

			frappe.call({
				method: "erpnext.selling.doctype.promotion.promotion.sync_diamond_collect",
				callback: (r) => {
					if (r.message) {
						frappe.msgprint(r.message);
					}
				},
				always: () => {
					$btn.prop("disabled", false);
					frappe.dom.unfreeze();
				}
			});
		}, 2000));
	}
};



