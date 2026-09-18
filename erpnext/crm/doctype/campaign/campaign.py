# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Campaign(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.crm.doctype.campaign_email_schedule.campaign_email_schedule import (
			CampaignEmailSchedule,
		)
		from erpnext.crm.doctype.campaign_koc.campaign_koc import CampaignKOC

		campaign_name: DF.Data
		campaign_schedules: DF.Table[CampaignEmailSchedule]
		campaign_type: DF.Literal["Livestream", "Email", "Social", "Other"]
		description: DF.Text | None
		end_time: DF.Datetime | None
		kocs: DF.Table[CampaignKOC]
		kocs_json: DF.JSON | None
		link_name: DF.DynamicLink | None
		link_type: DF.Link | None
		naming_series: DF.Literal["SAL-CAM-.YYYY.-"]
		platforms: DF.Data | None
		start_time: DF.Datetime | None
	# end: auto-generated types

	def before_save(self):
		self.render_kocs_json()

	def render_kocs_json(self):
		"""Serialize kocs child table into kocs_json field."""
		data = []
		if getattr(self, "kocs", None):
			for row in self.kocs:
				data.append({
					"koc": row.koc,
					"koc_name": row.koc_name,
					"commission_rate": float(row.commission_rate or 0),
					"notes": row.notes or "",
				})
		self.kocs_json = frappe.as_json(data)

	def get_koc_commission_rate(self, koc_id):
		"""Return the specific commission rate for a KOC in this campaign."""
		if getattr(self, "kocs", None):
			for row in self.kocs:
				if row.koc == koc_id:
					return float(row.commission_rate or 0)

		# Fallback to KOC master plan or default
		if koc_id:
			koc_doc = frappe.get_doc("KOC", koc_id)
			return koc_doc.get_commission_rate(self.start_time or self.creation)
		return 5.0

	def after_insert(self):
		self.sync_utm_campaign()

	def on_change(self):
		self.sync_utm_campaign()

	def sync_utm_campaign(self):
		if frappe.db.exists("UTM Campaign", self.campaign_name):
			mc = frappe.get_doc("UTM Campaign", self.campaign_name)
		else:
			mc = frappe.new_doc("UTM Campaign")
			mc.name = self.campaign_name
		mc.campaign_description = self.description
		mc.crm_campaign = self.campaign_name
		mc.save(ignore_permissions=True)
