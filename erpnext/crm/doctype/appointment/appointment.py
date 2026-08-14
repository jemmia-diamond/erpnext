# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


from collections import Counter
from datetime import timedelta
from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.desk.form.assign_to import add as add_assignment
from frappe.model.document import Document
from frappe.share import add_docshare
from frappe.utils import add_to_date, cint, date_diff, get_datetime, get_url, getdate, now, now_datetime
from frappe.utils.verified_command import get_signed_params
from frappe.utils.data import sha256_hash
from frappe.utils.html_utils import escape_html
from erpnext.utilities.phone_utils import get_phone_variants, search_doc_by_phone
from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

class Appointment(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from erpnext.crm.doctype.appointment_policy.appointment_policy import AppointmentPolicy
		from erpnext.crm.doctype.appointment_sales_person.appointment_sales_person import AppointmentSalesPerson
		from erpnext.crm.doctype.lead_product_item.lead_product_item import LeadProductItem
		from frappe.types import DF

		appointment_reason: DF.Literal["Warranty Service", "Trade-in", "Purchase", "Consultation", "Cleaning", "Other"]
		appointment_with: DF.Link | None
		at_store: DF.Literal["72 Nguy\u1ec5n C\u01b0 Trinh, Ph\u01b0\u1eddng B\u1ebfn Th\u00e0nh, TP H\u1ed3 Ch\u00ed Minh", "63 Kim M\u00e3, Ph\u01b0\u1eddng Gi\u1ea3ng V\u00f5, TP H\u00e0 N\u1ed9i", "209 \u0110\u01b0\u1eddng 30 Th\u00e1ng 4, Ph\u01b0\u1eddng Ninh Ki\u1ec1u, TP C\u1ea7n Th\u01a1"]
		auto_close: DF.Check
		budget: DF.Currency
		calendar_event: DF.Link | None
		conversation_greeting: DF.LongText | None
		created_at: DF.Datetime | None
		customer_email: DF.Data | None
		customer_name: DF.Data
		customer_phone_number: DF.Data | None
		customer_response: DF.LongText | None
		estimated_budget: DF.Link | None
		expected_delivery_date: DF.Date | None
		gender: DF.Link | None
		lead: DF.Link | None
		main_sales: DF.TableMultiSelect[AppointmentSalesPerson]
		message_id: DF.Data | None
		notes: DF.LongText | None
		offline_response: DF.LongText | None
		offline_sales: DF.TableMultiSelect[AppointmentSalesPerson]
		offline_sales_name: DF.Data | None
		order_status: DF.Literal["Kh\u00e1ch \u0111\u00e3 mua h\u00e0ng", "Kh\u00e1ch h\u1eb9n \u0111\u1ebfn c\u1eeda h\u00e0ng", "Kh\u00e1ch ch\u01b0a mua h\u00e0ng", "Kh\u00e1ch kh\u00f4ng \u0111\u1ebfn c\u1eeda h\u00e0ng", "Kh\u00e1ch ho\u00e3n l\u1ea1i ng\u00e0y \u0111\u1ebfn c\u1eeda h\u00e0ng", "Kh\u00e1ch \u0111\u00e3 \u0111\u1ebfn c\u1eeda h\u00e0ng"]
		created_through_portal: DF.Check
		email_verified: DF.Check
		party: DF.DynamicLink | None
		performed_by: DF.Data | None
		policies: DF.TableMultiSelect[AppointmentPolicy]
		policy: DF.LongText | None
		preferred_products: DF.TableMultiSelect[LeadProductItem]
		primary_sales: DF.Link | None
		primary_sales_name: DF.Data | None
		purchase_purpose: DF.Link | None
		range_estimated_budget: DF.Link | None
		record_id: DF.Data | None
		scheduled_time: DF.Datetime
		source: DF.Link | None
		source_name: DF.Data | None
		status: DF.Literal["Open", "Cancelled", "Done"]
		store: DF.Literal["72 NCT", "63 KM", "C\u1ea7n Th\u01a1"]
		verification_token: DF.Data | None
	# end: auto-generated types

	def validate(self):
		# self.validate_status_update()
		# if not self.has_value_changed("scheduled_time"):
		# 	return

		# self.validate_backdated_booking()

		# if is_appointment_scheduling_enabled():
		# 	self.validate_advanced_booking()
		# 	self.validate_holiday()
		# 	self.validate_slot_timing()

		# self.validate_available_time_slot()

	def validate_status_update(self):
		if not self.has_value_changed("status"):
			return

		if not self.created_through_portal:
			if self.status == "Unverified":
				frappe.throw(_("Appointments created manually cannot have 'Unverified' status."))
			return

		if self.status == "Unverified" and self.email_verified:
			frappe.throw(_("A verified appointment cannot be moved back to 'Unverified' status."))

		if self.status == "Open" and not self.email_verified:
			frappe.throw(
				_("An appointment booked through the portal can only be opened via email verification.")
			)

	def validate_backdated_booking(self):
		if get_datetime(self.scheduled_time) < now_datetime():
			frappe.throw(_("Appointment cannot be scheduled for a past time."))

	def validate_advanced_booking(self):
		advance_booking_days = cint(get_booking_settings().advance_booking_days)

		if advance_booking_days and date_diff(self.scheduled_time, now_datetime()) > advance_booking_days:
			frappe.throw(
				_("Appointment can only be scheduled up to {0} day(s) in advance.").format(
					advance_booking_days
				)
			)

	def validate_holiday(self):
		holiday_list = get_booking_settings().holiday_list

		if not holiday_list:
			frappe.throw(_("Please add a valid Holiday List on Appointment Booking Settings."))

		if is_holiday(holiday_list, getdate(self.scheduled_time)):
			frappe.throw(_("Appointment cannot be scheduled on a holiday."))

	def validate_slot_timing(self):
		settings = get_booking_settings()
		if not settings.availability_of_slots:
			frappe.throw(_("No availability of slots are found. Please add on Appointment Booking Settings."))

		scheduled_time = get_datetime(self.scheduled_time)
		day_of_week = WEEKDAYS[scheduled_time.weekday()]
		slot_start = timedelta(
			hours=scheduled_time.hour, minutes=scheduled_time.minute, seconds=scheduled_time.second
		)
		slot_end = slot_start + timedelta(minutes=cint(settings.appointment_duration))

		for slot in settings.availability_of_slots:
			if slot.day_of_week == day_of_week and slot.from_time <= slot_start and slot_end <= slot.to_time:
				return

		frappe.throw(_("Appointment must be scheduled within the available slot timings."))

	def validate_available_time_slot(self):
		settings = get_booking_settings()
		if not cint(settings.number_of_agents):
			return

		# the locking read serializes concurrent bookings for the same window,
		# so two simultaneous requests cannot both pass the capacity check
		booked = count_overlapping_appointments(
			self.scheduled_time,
			cint(settings.appointment_duration),
			exclude_appointment=self.name,
			for_update=True,
		)

		if booked >= cint(settings.number_of_agents):
			frappe.throw(_("Time slot is not available"))

	@frappe.whitelist()
	def handle_missing_party_or_source(self):
		if not self.party or not self.appointment_with:
			if self.customer_phone_number:
				doctype, docname = search_doc_by_phone(self.customer_phone_number, ["Customer", "Lead"])
				if doctype and docname:
					self.appointment_with = doctype
					self.party = docname

		if self.party and not self.source:
			self.handle_missing_source()

	def handle_missing_source(self):
		if self.appointment_with == "Customer":
			first_source, lead_name = frappe.db.get_value(
				"Customer", self.party, ["first_source", "lead_name"]
			) or (None, None)
			
			if first_source:
				self.source = first_source
			elif lead_name:
				self.source = frappe.db.get_value("Lead", lead_name, "source")
			else:
				customer = frappe.get_doc("Customer", self.party)
				phone_to_check = customer.normalized_phone or customer.phone or customer.mobile_no
				if phone_to_check:
					doctype, docname = search_doc_by_phone(phone_to_check, ["Lead"])
					if docname:
						self.source = frappe.db.get_value("Lead", docname, "source")
						
		elif self.appointment_with == "Lead":
			self.source = frappe.db.get_value("Lead", self.party, "source")

	def before_save(self):
		if self.status in ["Closed", "Close"]:
			self.status = "Done"

		if frappe.session.user != "tech@jemmia.vn":
			self.performed_by = frappe.session.user
		elif self.performed_by and "@" not in self.performed_by:
			email = frappe.db.get_value("Sales Person", {"name": self.performed_by}, "employee_email")
			self.performed_by = email or "tech@jemmia.vn"

		if self.offline_sales:
			names = [d.sales_person_name for d in self.offline_sales if d.sales_person_name]
			self.offline_sales_name = ", ".join(names)

		if not self.party or not self.appointment_with or not self.source:
			self.handle_missing_party_or_source()

	def before_insert(self):
		# # Set status to "Unverified" for new Appointments.
		# if self.created_through_portal:
		# 	self.status = "Unverified"
		# 	return
		# number_of_appointments_in_same_slot = frappe.db.count(
		# 	"Appointment", filters={"scheduled_time": self.scheduled_time}
		# )
		# number_of_agents = frappe.db.get_single_value("Appointment Booking Settings", "number_of_agents")
		# if number_of_agents != 0:
		# 	if number_of_appointments_in_same_slot >= number_of_agents:
		# 		frappe.throw(_("Time slot is not available"))
		# Link lead or customer ( API Flow )
		if not self.party:
			if not self.appointment_with:
				if self.customer_phone_number:
					variants = get_phone_variants(self.customer_phone_number)
					
					customer = frappe.db.get_value("Customer", {"mobile_no": ("in", variants)}, "name")
					if not customer:
						customer = frappe.db.get_value("Customer", {"phone": ("in", variants)}, "name")
						
					if customer:
						self.appointment_with = "Customer"
						self.party = customer
					else:
						lead = frappe.db.get_value("Lead", {"phone": ("in", variants)}, "name")
						if not lead:
							lead = frappe.db.get_value("Lead", {"mobile_no": ("in", variants)}, "name")
						if lead:
							self.appointment_with = "Lead"
							self.party = lead
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
		# if self.party:
		# 	# Auto assign agent
		# 	# self.auto_assign()
		# 	# self.create_calendar_event()
		# else:
		# 	# Set status to unverified
		# 	self.db_set("status", "Unverified")
		# 	# Send email to confirm
		# 	self.send_confirmation_email()
		pass

	def on_update(self):
		# capture transitions before nested saves during materialization
		# refresh the before-save snapshot
		# status_changed = self.has_value_changed("status")
		# email_just_verified = bool(
		# 	self.created_through_portal and self.email_verified
		# ) and self.has_value_changed("email_verified")

		# self.link_auto_assign_and_create_calendar_event()

		# if email_just_verified:
		# 	self.send_appointment_confirmed_email()

		# if status_changed:
		# 	self.update_event_and_assignments_status()
		pass

	def on_trash(self):
		# the Event only references the party, not the appointment,
		# so it must be cleaned up explicitly
		# if not self.calendar_event:
		# 	return

		# event = self.calendar_event
		# self.db_set("calendar_event", None, update_modified=False)
		# frappe.delete_doc("Event", event, ignore_permissions=True)
		pass

	def send_confirmation_email(self):
		self.send_email_to_customer(
			template="confirm_appointment",
			subject=_("Appointment Confirmation"),
			args={"link": self._get_verify_url(), "expiry_minutes": get_verification_link_expiry()},
		)
		frappe.msgprint(_("Please check your email to confirm the appointment."))

	def send_appointment_confirmed_email(self):
		self.send_email_to_customer(
			template="appointment_confirmed",
			subject=_("Appointment Confirmed"),
			args={"scheduled_time": frappe.utils.format_datetime(self.scheduled_time)},
			reference_doctype="Appointment",
			reference_name=self.name,
		)

	def send_email_to_customer(self, template, subject, args, **kwargs):
		frappe.sendmail(
			recipients=[self.customer_email],
			template=template,
			args={"full_name": self.customer_name, "site_url": frappe.utils.get_url(), **args},
			subject=subject,
			**kwargs,
		)

	def link_auto_assign_and_create_calendar_event(self):
		if self.is_new() or (self.created_through_portal and not self.email_verified):
			return

		if not self.calendar_event:
			# first materialization: link the party, assign an agent, create the event
			self.link_customer_lead()
			self.auto_assign()
			self.create_calendar_event()

		self.sync_calendar_event()

	def sync_calendar_event(self):
		if not self.calendar_event or not self.has_value_changed("scheduled_time"):
			return

		cal_event = frappe.get_doc("Event", self.calendar_event)
		cal_event.starts_on = self.scheduled_time
		cal_event.save(ignore_permissions=True)

	def update_event_and_assignments_status(self):
		"""Close or reopen the calendar event and assignments along with the appointment."""
		if self.status == "Unverified":
			return

		is_closed = self.status == "Closed"
		new_status = "Closed" if is_closed else "Open"

		if self.calendar_event:
			frappe.db.set_value("Event", self.calendar_event, "status", new_status)

		# only move ToDos between Open and Closed - never touch Cancelled ones
		todo_filters = {
			"reference_type": "Appointment",
			"reference_name": self.name,
			"status": "Open" if is_closed else "Closed",
		}
		frappe.db.set_value("ToDo", todo_filters, "status", new_status)

	def link_customer_lead(self):
		if not self.party:
			customer = self.find_party_by_email("Customer")
			self.appointment_with = "Customer" if customer else "Lead"
			self.party = customer or self.find_party_by_email("Lead")

		self.create_lead_and_link()

	def find_party_by_email(self, doctype):
		party = frappe.get_all(doctype, filters={"email_id": self.customer_email}, limit=1, pluck="name")
		return party[0] if party else None

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
					"note": escape_html(self.conversation_greeting),
					"added_by": frappe.session.user,
					"added_on": now(),
				},
			)

		self.party = lead.insert(ignore_permissions=True).name

	def auto_assign(self):
		if self._assign:
			return

		if existing_assignee := self.get_assignee_from_latest_opportunity():
			# assign to whoever handles the party's latest opportunity
			self.assign_agent(existing_assignee)
			return

		busy_agents = get_busy_agents(self.scheduled_time)
		for agent in _get_agents_sorted_by_asc_workload(getdate(self.scheduled_time)):
			if agent not in busy_agents:
				self.assign_agent(agent)
				break

	def get_assignee_from_latest_opportunity(self):
		if not self.party or not frappe.db.exists("Lead", self.party):
			return None

		opportunities = frappe.get_all(
			"Opportunity",
			filters={"party_name": self.party},
			fields=["_assign"],
			order_by="creation desc",
			limit=1,
		)
		assignees = opportunities and frappe.parse_json(opportunities[0]._assign or "[]")
		return assignees[0] if assignees else None

	def assign_agent(self, agent):
		if not frappe.has_permission(doc=self, user=agent):
			add_docshare(self.doctype, self.name, agent, flags={"ignore_share_permission": True})

		add_assignment({"doctype": self.doctype, "name": self.name, "assign_to": [agent]})

	def create_calendar_event(self):
		if self.calendar_event:
			return

		event = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": f"Appointment with {self.customer_name}",
				"starts_on": self.scheduled_time,
				"status": "Open",
				"type": "Public",
				"send_reminder": cint(get_booking_settings().email_reminders),
				"event_participants": self.get_event_participants(),
			}
		).insert(ignore_permissions=True)

		self.calendar_event = event.name
		self.save(ignore_permissions=True)

	def get_event_participants(self):
		participants = [dict(reference_doctype=self.appointment_with, reference_docname=self.party)]

		if employee := _get_employee_from_user(self._assign):
			participants.append(dict(reference_doctype="Employee", reference_docname=employee.name))

		return participants

	def _get_verify_url(self):
		key = self.generate_verification_key()
		return get_url("/book_appointment/verify?" + urlencode({"key": key}))

	def generate_verification_key(self):
		# store only the hash; the raw key lives solely in the emailed link
		key = frappe.generate_hash()
		self.db_set("verification_token", sha256_hash(key), update_modified=False)
		return key


def get_booking_settings():
	return frappe.get_cached_doc("Appointment Booking Settings")


def is_appointment_scheduling_enabled():
	return bool(cint(get_booking_settings().enable_scheduling))


def get_verification_link_expiry():
	"""Verification link expiry window in minutes."""
	return cint(get_booking_settings().verification_link_expiry_duration)


def count_overlapping_appointments(
	scheduled_time, appointment_duration, exclude_appointment=None, for_update=False
):
	"""Count non-Closed appointments whose duration window overlaps `scheduled_time`.
	With `for_update`, the range stays locked until commit, serializing concurrent bookings."""
	# select the rows (not COUNT) so `for_update` stays valid: PostgreSQL
	# rejects `FOR UPDATE` combined with an aggregate function
	appointment = frappe.qb.DocType("Appointment")
	query = (
		frappe.qb.from_(appointment)
		.select(appointment.name)
		.where(appointment.scheduled_time > add_to_date(scheduled_time, minutes=-appointment_duration))
		.where(appointment.scheduled_time < add_to_date(scheduled_time, minutes=appointment_duration))
		.where(appointment.status != "Closed")
	)

	if exclude_appointment:
		query = query.where(appointment.name != exclude_appointment)

	if for_update:
		query = query.for_update()

	return len(query.run())


def handle_expired_unverified_appointments():
	"""Close or delete Unverified appointments whose verification link has expired."""
	expiry = get_verification_link_expiry()
	if not expiry:
		return

	cutoff = add_to_date(now_datetime(), minutes=-expiry)
	filters = {"status": "Unverified", "creation": ("<", cutoff)}
	action = get_booking_settings().action_for_expired_unverified_appointments or "Mark as Closed"

	if action == "Mark as Closed":
		frappe.db.set_value("Appointment", filters, "status", "Closed")
	elif action == "Delete Permanently":
		for name in frappe.get_all("Appointment", filters=filters, pluck="name"):
			frappe.delete_doc("Appointment", name, ignore_permissions=True)


def _get_agents_sorted_by_asc_workload(date):
	# count only the given day's assignments; scheduled_time is indexed so the
	# date range is resolved in SQL instead of scanning every appointment ever
	workload = Counter(agent.user for agent in get_booking_settings().agent_list)
	assigns = frappe.get_all(
		"Appointment",
		filters=[
			["_assign", "is", "set"],
			["scheduled_time", ">=", getdate(date)],
			["scheduled_time", "<", add_to_date(getdate(date), days=1)],
		],
		pluck="_assign",
	)

	for assign in assigns:
		assignees = frappe.parse_json((assign or "").strip() or "[]")
		if assignees and assignees[0] in workload:
			workload[assignees[0]] += 1

	return [agent for agent, _workload in reversed(workload.most_common())]


def get_busy_agents(scheduled_time):
	"""Agents already assigned to a non-Closed appointment overlapping `scheduled_time`."""
	duration = _get_appointment_duration()
	assigns = frappe.get_all(
		"Appointment",
		filters=[
			["scheduled_time", ">", add_to_date(scheduled_time, minutes=-duration)],
			["scheduled_time", "<", add_to_date(scheduled_time, minutes=duration)],
			["status", "!=", "Closed"],
		],
		pluck="_assign",
	)
	return {assignee for assign in assigns for assignee in frappe.parse_json(assign or "[]")}


def _check_agent_availability(agent_email, scheduled_time):
	return agent_email not in get_busy_agents(scheduled_time)


def get_booked_slot_times(from_time, to_time):
	"""scheduled_times of non-Closed appointments within (from_time, to_time), for slot availability."""
	return frappe.get_all(
		"Appointment",
		filters=[
			["scheduled_time", ">", from_time],
			["scheduled_time", "<", to_time],
			["status", "!=", "Closed"],
		],
		pluck="scheduled_time",
	)


def _get_appointment_duration():
	return cint(get_booking_settings().appointment_duration)


def _get_employee_from_user(user):
	employee_docname = frappe.db.get_value("Employee", {"user_id": user})
	return frappe.get_doc("Employee", employee_docname) if employee_docname else None
