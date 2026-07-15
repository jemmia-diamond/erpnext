# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.contacts.doctype.contact.contact import get_contact_with_phone_number
from frappe.core.doctype.dynamic_link.dynamic_link import deduplicate_dynamic_links
from frappe.model.document import Document
from frappe.utils.file_manager import get_file, save_file
from erpnext.crm.doctype.lead.lead import get_lead_with_phone_number
from erpnext.crm.doctype.utils import get_scheduled_employees_for_popup, strip_number
from erpnext.config.config import config
from erpnext.utilities.phone_utils import get_phone_variants

import jwt
import time
import requests

END_CALL_STATUSES = ["No Answer", "Completed", "Busy", "Failed"]
ONGOING_CALL_STATUSES = ["Ringing", "In Progress"]


class CallLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.dynamic_link.dynamic_link import DynamicLink
		from frappe.types import DF

		agent_id: DF.Data | None
		agent_name: DF.Data | None
		ai_action_item_text: DF.LongText | None
		ai_summary: DF.LongText | None
		call_received_by: DF.Link | None
		customer_sentinent: DF.Literal["Can't detect", "Happy", "Neutral", "Frustrated", "Angry", "Confused", "Concerned", "Excited", "Impatient"]
		disposition: DF.Data | None
		duration: DF.Duration | None
		employee_user_id: DF.Link | None
		end_time: DF.Datetime | None
		id: DF.Data | None
		links: DF.Table[DynamicLink]
		medium: DF.Data | None
		participant: DF.DynamicLink | None
		participant_type: DF.Link | None
		provider: DF.Data | None
		recording_url: DF.Data | None
		start_time: DF.Datetime | None
		status: DF.Literal["Ringing", "In Progress", "Completed", "Failed", "Busy", "No Answer", "Queued", "Cancelled"]
		summary: DF.SmallText | None
		text_extracted: DF.LongText | None
		to: DF.Data | None
		type: DF.Literal["Incoming", "Outgoing"]
		type_of_call: DF.Link | None
	# end: auto-generated types

	def validate(self):
		deduplicate_dynamic_links(self)

	def before_insert(self):
		"""Add lead(third party person) links to the document."""
		lead_number = self.get("from") if self.is_incoming_call() else self.get("to")
		lead_number = strip_number(lead_number)

		if contact := get_contact_with_phone_number(strip_number(lead_number)):
			self.add_link(link_type="Contact", link_name=contact)

		if lead := get_lead_with_phone_number(lead_number):
			self.add_link(link_type="Lead", link_name=lead)

		# Add Employee Name
		self.update_received_by()

	def after_insert(self):
		self.update_participant_if_missing()
		self.trigger_call_popup()
		if self.recording_url:
			frappe.enqueue(
				"erpnext.telephony.doctype.call_log.call_log.download_and_attach_recording",
				call_log_name=self.name,
				queue="short",
				enqueue_after_commit=True
			)

	def on_update(self):
		self.update_participant_if_missing()

		def _is_call_missed(doc_before_save, doc_after_save):
			# FIXME: This works for Exotel but not for all telepony providers
			return doc_before_save.to != doc_after_save.to and doc_after_save.status not in END_CALL_STATUSES

		def _is_call_ended(doc_before_save, doc_after_save):
			return doc_before_save.status not in END_CALL_STATUSES and self.status in END_CALL_STATUSES

		doc_before_save = self.get_doc_before_save()
		if not doc_before_save:
			return

		if self.is_incoming_call() and self.has_value_changed("to"):
			self.update_received_by()

		if _is_call_missed(doc_before_save, self):
			frappe.publish_realtime(f"call_{self.id}_missed", self)
			self.trigger_call_popup()

		if _is_call_ended(doc_before_save, self):
			frappe.publish_realtime(f"call_{self.id}_ended", self)

		if self.recording_url and doc_before_save.recording_url != self.recording_url:
			frappe.enqueue(
				"erpnext.telephony.doctype.call_log.call_log.download_and_attach_recording",
				call_log_name=self.name,
				queue="short"
			)

	def is_incoming_call(self):
		return self.type == "Incoming"

	def update_participant_if_missing(self):
		if self.participant:
			return

		format_phone = self.get("from") if self.is_incoming_call() else self.get("to")
		if not format_phone:
			return

		variants = get_phone_variants(format_phone)
		customers = frappe.get_all(
			"Customer",
			or_filters={"mobile_no": ["in", variants], "phone": ["in", variants]},
			fields=["name"],
			limit=1
		)
		if customers:
			self.participant_type = "Customer"
			self.participant = customers[0].name
			frappe.db.set_value(self.doctype, self.name, {
				"participant_type": "Customer",
				"participant": customers[0].name
			})
			return

		leads = frappe.get_all(
			"Lead",
			or_filters={"mobile_no": ["in", variants], "phone": ["in", variants]},
			fields=["name"],
			limit=1
		)
		if leads:
			self.participant_type = "Lead"
			self.participant = leads[0].name
			frappe.db.set_value(self.doctype, self.name, {
				"participant_type": "Lead",
				"participant": leads[0].name
			})

	def add_link(self, link_type, link_name):
		self.append("links", {"link_doctype": link_type, "link_name": link_name})

	def trigger_call_popup(self):
		if not self.is_incoming_call():
			return

		scheduled_employees = get_scheduled_employees_for_popup(self.medium)
		employees = get_employees_with_number(self.to)
		employee_emails = [employee.get("user_id") for employee in employees]

		# check if employees with matched number are scheduled to receive popup
		emails = set(scheduled_employees).intersection(employee_emails)

		if frappe.conf.developer_mode:
			self.add_comment(
				text=f"""
					Scheduled Employees: {scheduled_employees}
					Matching Employee: {employee_emails}
					Show Popup To: {emails}
				"""
			)

		if employee_emails and not emails:
			self.add_comment(text=_("No employee was scheduled for call popup"))

		for email in emails:
			frappe.publish_realtime("show_call_popup", self, user=email)

	def update_received_by(self):
		if self.call_received_by or getattr(self, "provider", "stringee") != "vbot" or not self.agent_id:
			return

		employee_data = frappe.db.get_value("Employee", {"vbot_id": self.agent_id}, ["name", "employee_name", "user_id"], as_dict=True)
		if not employee_data:
			try:
				url = f"{config.VBOT_BASE_URL}/api/member/getByMemberNo?member_no={self.agent_id}"
				response = requests.get(url, headers={"X-API-Key": config.CC_API_KEY}, timeout=10)

				if response.ok and (member_name := (response.json().get("data") or {}).get("member_name")):
					self.agent_name = member_name
					if emp_data := frappe.db.get_value("Employee", {"employee_name": member_name}, ["name", "user_id"], as_dict=True):
						employee_data = {"name": emp_data.get("name"), "employee_name": member_name, "user_id": emp_data.get("user_id")}
						frappe.db.set_value("Employee", emp_data.get("name"), "vbot_id", self.agent_id)
			except Exception as e:
				frappe.log_error(f"Failed to fetch Vbot agent for Call Log {self.name}: {str(e)}", "Vbot Agent Lookup")

		if employee_data:
			self.agent_name = employee_data.get("employee_name")
			self.call_received_by = employee_data.get("name")
			self.employee_user_id = employee_data.get("user_id")
			self.agent_type = "User"
			self.agent = employee_data.get("user_id")


@frappe.whitelist()
def add_call_summary_and_call_type(call_log, summary, call_type):
	doc = frappe.get_doc("Call Log", call_log)
	doc.type_of_call = call_type
	doc.save()
	doc.add_comment("Comment", frappe.bold(_("Call Summary")) + "<br><br>" + summary)


def get_employees_with_number(number):
	number = strip_number(number)
	if not number:
		return []

	employee_doc_name_and_emails = frappe.cache().hget("employees_with_number", number)
	if employee_doc_name_and_emails:
		return employee_doc_name_and_emails

	employee_doc_name_and_emails = frappe.get_all(
		"Employee",
		filters={"cell_number": ["like", f"%{number}%"], "user_id": ["!=", ""]},
		fields=["name", "user_id"],
	)

	frappe.cache().hset("employees_with_number", number, employee_doc_name_and_emails)

	return employee_doc_name_and_emails


def link_existing_conversations(doc, state):
	"""
	Called from hooks on creation of Contact or Lead to link all the existing conversations.
	"""
	if doc.flags.ignore_auto_link_call_log:
		return
	if doc.doctype != "Contact":
		return
	try:
		numbers = [d.phone for d in doc.phone_nos]

		for number in numbers:
			number = strip_number(number)
			if not number:
				continue
			logs = frappe.db.sql_list(
				"""
				SELECT cl.name FROM `tabCall Log` cl
				LEFT JOIN `tabDynamic Link` dl
				ON cl.name = dl.parent
				WHERE (cl.`from` like %(phone_number)s or cl.`to` like %(phone_number)s)
				GROUP BY cl.name
				HAVING SUM(
					CASE
						WHEN dl.link_doctype = %(doctype)s AND dl.link_name = %(docname)s
						THEN 1
						ELSE 0
					END
				)=0
				""",
				dict(phone_number=f"%{number}", docname=doc.name, doctype=doc.doctype),
			)
			if logs:
				for log in logs:
					call_log = frappe.get_doc("Call Log", log)
					call_log.add_link(link_type=doc.doctype, link_name=doc.name)
					call_log.save(ignore_permissions=True)

				if not frappe.in_test:
					frappe.db.commit()
	except Exception:
		frappe.log_error(title=_("Error during caller information update"))


def get_linked_call_logs(doctype, docname):
	# content will be shown in timeline
	logs = frappe.get_all(
		"Dynamic Link",
		fields=["parent"],
		filters={"parenttype": "Call Log", "link_doctype": doctype, "link_name": docname},
	)
	if not logs:
		return []

	logs = {log.parent for log in logs}

	logs = frappe.get_all("Call Log", fields=["*"], filters={"name": ["in", logs]})

	timeline_contents = []
	for log in logs:
		log.show_call_button = 0
		timeline_contents.append(
			{
				"icon": "call",
				"is_card": True,
				"creation": log.creation,
				"template": "call_link",
				"template_data": log,
			}
		)

	return timeline_contents

@frappe.whitelist()
def get_stringee_access_token():
	now = int(time.time())
	exp_in_second = 30
	exp = now + exp_in_second
	payload = {
		"jti": f"{config.STRINGEE_API_KEY_SID}-{now}",
		"iss": config.STRINGEE_API_KEY_SID,
		"exp": exp,
		"rest_api": True
	}
	token = jwt.encode(payload, config.STRINGEE_API_KEY_SECRET, algorithm="HS256")
	return token

@frappe.whitelist()
def download_and_attach_recording(call_log_name):
	call_log = frappe.get_doc("Call Log", call_log_name)

	if not call_log.recording_url:
		return

	if frappe.db.exists("File", {"attached_to_doctype": "Call Log", "attached_to_name": call_log_name, "is_private": 1}):
		return

	headers = {}
	if getattr(call_log, "provider", "stringee") == "stringee":
		token = get_stringee_access_token()
		download_url = f"{call_log.recording_url}?access_token={token}"
	else:
		download_url = call_log.recording_url
		if config.CC_API_KEY:
			headers["X-API-Key"] = config.CC_API_KEY

	try:
		response = requests.get(download_url, headers=headers)
		if response.status_code == 200:
			save_file(
				fname=f"recording_{call_log.name}.mp3",
				content=response.content,
				dt="Call Log",
				dn=call_log.name,
				is_private=1
			)
			frappe.db.commit()
	except Exception as e:
		frappe.log_error(f"Failed to download recording for Call Log {call_log_name}: {str(e)}", "Call Log Recording Download")
