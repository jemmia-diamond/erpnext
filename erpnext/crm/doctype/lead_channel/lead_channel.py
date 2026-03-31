# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class LeadChannel(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		address: DF.Data | None
		email: DF.Data | None
		first_message_time: DF.Datetime | None
		full_name: DF.Data | None
		last_incoming_call_time: DF.Datetime | None
		last_message_time: DF.Datetime | None
		last_outgoing_call_time: DF.Datetime | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		phone: DF.Data | None
		phone_number_provided_time: DF.Datetime | None
		profile_url: DF.Data | None
		source: DF.Data | None
		source_group: DF.Literal["Facebook", "Zalo", "Tiktok", "Call Center", "Website Form", "Visiting Guests", "Email"]
		type: DF.Data | None
	# end: auto-generated types
	pass
