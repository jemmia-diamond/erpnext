frappe.listview_settings['Promotion'] = {
	onload: function(listview) {
		const btn_label = __('Đồng bộ CTKM nền');
		const $btn = listview.page.add_inner_button(btn_label, frappe.utils.debounce(() => {
			$btn.prop("disabled", true);
			frappe.dom.freeze(__('Đang đồng bộ...'));

			frappe.call({
				method: "erpnext.selling.doctype.promotion.promotion.sync_diamond_collect",
				callback: (r) => {
					if (r.message) {
						frappe.msgprint({
							message: r.message,
							indicator: 'green',
							title: __('Đồng bộ thành công')
						});
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
