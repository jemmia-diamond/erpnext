// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Call Log", {
	refresh: function (frm) {

		const incoming_call = frm.doc.type == "Incoming";
		// frm.add_custom_button(incoming_call ? __("Callback") : __("Call Again"), () => {
		// 	const number = incoming_call ? frm.doc.from : frm.doc.to;
		// 	frappe.phone_call.handler(number, frm);
		// });

		try {
			if (!frm.doc.provider || frm.doc.provider === "stringee") {
				frappe.call({
					method: "erpnext.telephony.doctype.call_log.call_log.get_stringee_access_token",
					callback: function (r) {
						frm.events.setup_recording_audio_control(frm, r.message);
					},
				});
			} else {
				frm.events.setup_recording_audio_control(frm, null);
			}
		} catch {}
	},
	setup_recording_audio_control(frm, accessToken) {
		const recording_wrapper = frm.get_field("recording_html").$wrapper;
		if (!frm.doc.recording_url) {
			recording_wrapper.empty();
		} else {
			let audio_src = frm.doc.recording_url;
			if (accessToken) {
				audio_src = `${frm.doc.recording_url}?access_token=${accessToken}`;
			}
			if (frm.attachments && frm.attachments.get_attachments) {
				const attachments = frm.attachments.get_attachments() || [];
				const attached_mp3 = attachments.find(f => f.file_url && f.file_name && f.file_name.startsWith("recording_"));
				if (attached_mp3) {
					audio_src = attached_mp3.file_url;
				} else if (!frm.__download_attempted) {
					frm.__download_attempted = true;
					frappe.call({
						method: "erpnext.telephony.doctype.call_log.call_log.download_and_attach_recording",
						args: { call_log_name: frm.doc.name },
						callback: function() {
							frm.reload_doc();
						}
					});
				}
			}

			recording_wrapper.addClass("input-max-width");
			recording_wrapper.html(`
				<audio
					controls
					src="${audio_src}">
				</audio>
			`);
		}
	},
});
