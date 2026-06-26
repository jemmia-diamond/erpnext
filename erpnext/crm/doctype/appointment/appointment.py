# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


from collections import Counter

import frappe
from frappe import _
from frappe.desk.form.assign_to import add as add_assignment
from frappe.model.document import Document
from frappe.share import add_docshare
from frappe.utils import get_url, getdate, now
from frappe.utils.verified_command import get_signed_params


class Appointment(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from erpnext.crm.doctype.appointment_sales_person.appointment_sales_person import AppointmentSalesPerson
		from erpnext.crm.doctype.lead_product_item.lead_product_item import LeadProductItem
		from frappe.types import DF

		appointment_policy: DF.Link | None
		appointment_reason: DF.Literal["Warranty Service", "Trade-in", "Purchase", "Consultation", "Cleaning", "Other"]
		appointment_with: DF.Link | None
		at_store: DF.Literal["72 Nguy\u1ec5n C\u01b0 Trinh, Ph\u01b0\u1eddng B\u1ebfn Th\u00e0nh, TP H\u1ed3 Ch\u00ed Minh", "63 Kim M\u00e3, Ph\u01b0\u1eddng Gi\u1ea3ng V\u00f5, TP H\u00e0 N\u1ed9i", "209 \u0110\u01b0\u1eddng 30 Th\u00e1ng 4, Ph\u01b0\u1eddng Ninh Ki\u1ec1u, TP C\u1ea7n Th\u01a1"]
		auto_close: DF.Check
		budget: DF.Currency
		calendar_event: DF.Link | None
		conversation_greeting: DF.LongText | None
		customer_email: DF.Data | None
		customer_name: DF.Data
		customer_phone_number: DF.Data | None
		customer_response: DF.LongText | None
		estimated_budget: DF.Link | None
		expected_delivery_date: DF.Date | None
		gender: DF.Link | None
		lead: DF.Link | None
		main_sales: DF.TableMultiSelect[AppointmentSalesPerson]
		notes: DF.TextEditor | None
		offline_response: DF.TextEditor | None
		offline_sales: DF.TableMultiSelect[AppointmentSalesPerson]
		party: DF.DynamicLink | None
		policy: DF.LongText | None
		preferred_products: DF.TableMultiSelect[LeadProductItem]
		purchase_purpose: DF.Link | None
		range_estimated_budget: DF.Link | None
		record_id: DF.Data | None
		scheduled_time: DF.Datetime
		status: DF.Literal["Open", "Cancelled", "Closed"]
		store: DF.Literal["72 NCT", "63 KM", "C\u1ea7n Th\u01a1"]
	# end: auto-generated types

	def find_lead_by_email(self):
		lead_list = frappe.get_list(
			"Lead", filters={"email_id": self.customer_email}, ignore_permissions=True
		)
		if lead_list:
			return lead_list[0].name
		return None

	def find_customer_by_email(self):
		customer_list = frappe.get_list(
			"Customer", filters={"email_id": self.customer_email}, ignore_permissions=True
		)
		if customer_list:
			return customer_list[0].name
		return None

	def before_insert(self):
		number_of_appointments_in_same_slot = frappe.db.count(
			"Appointment", filters={"scheduled_time": self.scheduled_time}
		)
		number_of_agents = frappe.db.get_single_value("Appointment Booking Settings", "number_of_agents")
		if number_of_agents != 0:
			if number_of_appointments_in_same_slot >= number_of_agents:
				frappe.throw(_("Time slot is not available"))
		# Link lead or customer ( API Flow )
		if not self.party:
			if not self.appointment_with:
				if self.customer_phone_number:
					lead = frappe.db.get_value("Lead", {"phone": self.customer_phone_number}, "name")
					if lead:
						self.appointment_with = "Lead"
						self.party = lead
					else:
						customer = frappe.db.get_value("Customer", {"mobile_no": self.customer_phone_number}, "name")
						if not customer:
							customer = frappe.db.get_value("Customer", {"phone": self.customer_phone_number}, "name")
						if customer:
							self.appointment_with = "Customer"
							self.party = customer
			else:
				lead = self.find_lead_by_email()
				customer = self.find_customer_by_email()
				if customer:
					self.appointment_with = "Customer"
					self.party = customer
				elif lead:
					self.appointment_with = "Lead"
					self.party = lead

		if self.appointment_with == "Lead" and self.party:
			lead_doc = frappe.get_doc("Lead", self.party)
			if not self.expected_delivery_date and lead_doc.expected_delivery_date:
				self.expected_delivery_date = lead_doc.expected_delivery_date
			if not self.purchase_purpose and lead_doc.purpose_lead:
				self.purchase_purpose = lead_doc.purpose_lead
			if not self.preferred_products and lead_doc.preferred_product_type:
				self.preferred_products = lead_doc.preferred_product_type
			if self.meta.has_field("customer_status") and not self.get("customer_status"):
				self.customer_status = "Khách hẹn đến cửa hàng"

		if not self.at_store and self.store:
			if self.store == "72 NCT":
				self.at_store = "72 Nguyễn Cư Trinh, Phường Bến Thành, TP Hồ Chí Minh"
			elif self.store == "63 KM":
				self.at_store = "63 Kim Mã, Phường Giảng Võ, TP Hà Nội"
			elif self.store == "Cần Thơ":
				self.at_store = "209 Đường 30 Tháng 4, Phường Ninh Kiều, TP Cần Thơ"

		if not self.store and self.at_store:
			if "72 Nguyễn Cư Trinh" in self.at_store:
				self.store = "72 NCT"
			elif "63 Kim Mã" in self.at_store:
				self.store = "63 KM"
			elif "Cần Thơ" in self.at_store:
				self.store = "Cần Thơ"

	def after_insert(self):
		if self.party:
			# Create Calendar event
			self.auto_assign()
			self.create_calendar_event()
		else:
			# Set status to unverified
			self.db_set("status", "Unverified")
			# Send email to confirm
			self.send_confirmation_email()

	def send_confirmation_email(self):
		verify_url = self._get_verify_url()
		template = "confirm_appointment"
		args = {
			"link": verify_url,
			"site_url": frappe.utils.get_url(),
			"full_name": self.customer_name,
		}
		frappe.sendmail(
			recipients=[self.customer_email],
			template=template,
			args=args,
			subject=_("Appointment Confirmation"),
		)
		if frappe.session.user == "Guest":
			frappe.msgprint(_("Please check your email to confirm the appointment"))
		else:
			frappe.msgprint(
				_("Appointment was created. But no lead was found. Please check the email to confirm")
			)

	def on_change(self):
		# Sync Calendar
		if not self.calendar_event:
			return
		cal_event = frappe.get_doc("Event", self.calendar_event)
		cal_event.starts_on = self.scheduled_time
		cal_event.save(ignore_permissions=True)

	def set_verified(self, email):
		if email != self.customer_email:
			frappe.throw(_("Email verification failed."))
		# Create new lead
		self.create_lead_and_link()
		# Remove unverified status
		self.status = "Kh\u00e1ch \u0111\u00e3 mua h\u00e0ng"
		# Create calender event
		self.auto_assign()
		self.create_calendar_event()
		self.save(ignore_permissions=True)
		if not frappe.in_test:
			frappe.db.commit()

	def create_lead_and_link(self):
		# Return if already linked
		if self.party:
			return

		lead = frappe.get_doc(
			{
				"doctype": "Lead",
				"lead_name": self.customer_name,
				"email_id": self.customer_email,
				"phone": self.customer_phone_number,
			}
		)

		if self.conversation_greeting:
			lead.append(
				"notes",
				{
					"note": self.conversation_greeting,
					"added_by": frappe.session.user,
					"added_on": now(),
				},
			)

		lead.insert(ignore_permissions=True)

		# Link lead
		self.party = lead.name

	def auto_assign(self):
		existing_assignee = self.get_assignee_from_latest_opportunity()
		if existing_assignee:
			# If the latest opportunity is assigned to someone
			# Assign the appointment to the same
			self.assign_agent(existing_assignee)
			return
		if self._assign:
			return
		available_agents = _get_agents_sorted_by_asc_workload(getdate(self.scheduled_time))
		for agent in available_agents:
			if _check_agent_availability(agent, self.scheduled_time):
				self.assign_agent(agent[0])
			break

	def get_assignee_from_latest_opportunity(self):
		if not self.party:
			return None
		if not frappe.db.exists("Lead", self.party):
			return None
		opporutnities = frappe.get_list(
			"Opportunity",
			filters={
				"party_name": self.party,
			},
			ignore_permissions=True,
			order_by="creation desc",
		)
		if not opporutnities:
			return None
		latest_opportunity = frappe.get_doc("Opportunity", opporutnities[0].name)
		assignee = latest_opportunity._assign
		if not assignee:
			return None
		assignee = frappe.parse_json(assignee)[0]
		return assignee

	def create_calendar_event(self):
		if self.calendar_event:
			return
		appointment_event = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": " ".join(["Appointment with", self.customer_name]),
				"starts_on": self.scheduled_time,
				"status": "Open",
				"type": "Public",
				"send_reminder": frappe.db.get_single_value(
					"Appointment Booking Settings", "email_reminders"
				),
				"event_participants": [
					dict(reference_doctype=self.appointment_with, reference_docname=self.party)
				],
			}
		)
		employee = _get_employee_from_user(self._assign)
		if employee:
			appointment_event.append(
				"event_participants", dict(reference_doctype="Employee", reference_docname=employee.name)
			)
		appointment_event.insert(ignore_permissions=True)
		self.calendar_event = appointment_event.name
		self.save(ignore_permissions=True)

	def _get_verify_url(self):
		verify_route = "/book_appointment/verify"
		params = {"email": self.customer_email, "appointment": self.name}
		return get_url(verify_route + "?" + get_signed_params(params))

	def assign_agent(self, agent):
		if not frappe.has_permission(doc=self, user=agent):
			add_docshare(self.doctype, self.name, agent, flags={"ignore_share_permission": True})

		add_assignment({"doctype": self.doctype, "name": self.name, "assign_to": [agent]})


def _get_agents_sorted_by_asc_workload(date):
	appointments = frappe.get_all("Appointment", fields="*")
	agent_list = _get_agent_list_as_strings()
	if not appointments:
		return agent_list
	appointment_counter = Counter(agent_list)
	for appointment in appointments:
		assigned_to = frappe.parse_json(appointment._assign)
		if not assigned_to:
			continue
		if (assigned_to[0] in agent_list) and getdate(appointment.scheduled_time) == date:
			appointment_counter[assigned_to[0]] += 1
	sorted_agent_list = appointment_counter.most_common()
	sorted_agent_list.reverse()
	return sorted_agent_list


def _get_agent_list_as_strings():
	agent_list_as_strings = []
	agent_list = frappe.get_doc("Appointment Booking Settings").agent_list
	for agent in agent_list:
		agent_list_as_strings.append(agent.user)
	return agent_list_as_strings


def _check_agent_availability(agent_email, scheduled_time):
	appointemnts_at_scheduled_time = frappe.get_all("Appointment", filters={"scheduled_time": scheduled_time})
	for appointment in appointemnts_at_scheduled_time:
		if appointment._assign == agent_email:
			return False
	return True


def _get_employee_from_user(user):
	employee_docname = frappe.db.get_value("Employee", {"user_id": user})
	if employee_docname:
		return frappe.get_doc("Employee", employee_docname)
	return None
