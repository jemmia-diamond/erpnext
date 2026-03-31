// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Call Log", {
	refresh: function (frm) {

		const incoming_call = frm.doc.type == "Incoming";
		frm.add_custom_button(incoming_call ? __("Callback") : __("Call Again"), () => {
			const number = incoming_call ? frm.doc.from : frm.doc.to;
			frappe.phone_call.handler(number, frm);
		});

		try {
			frappe.call({
				method: "erpnext.telephony.doctype.call_log.call_log.get_access_token",
				callback: function (r) {
					frm.events.setup_recording_audio_control(frm, r.message);
				},
			});
		} catch {}
	},
	setup_recording_audio_control(frm, accessToken) {
		const recording_wrapper = frm.get_field("recording_html").$wrapper;
		if (!frm.doc.recording_url || frm.doc.recording_url == "null") {
			recording_wrapper.empty();
		} else {
			recording_wrapper.addClass("input-max-width");
			recording_wrapper.html(`
				<audio
					controls
					src="${frm.doc.recording_url}?access_token=${accessToken}">
				</audio>
			`);
		}
	},
});
