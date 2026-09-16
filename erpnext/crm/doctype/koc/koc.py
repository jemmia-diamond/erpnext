# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class KOC(Document):
	def validate(self):
		self.clean_slugs()
		if not self.attribution_window_days or self.attribution_window_days <= 0:
			self.attribution_window_days = 30

	def clean_slugs(self):
		"""Normalize slugs to comma-separated lowercase strings without extra whitespace."""
		if self.slugs:
			slug_list = [s.strip().lower() for s in self.slugs.replace("\n", ",").split(",") if s.strip()]
			# deduplicate while preserving order
			seen = set()
			unique_slugs = [s for s in slug_list if not (s in seen or seen.add(s))]
			self.slugs = ", ".join(unique_slugs)

	def get_active_campaigns(self):
		"""Return all ongoing livestream campaigns for this KOC."""
		now = frappe.utils.now_datetime()
		return frappe.get_all(
			"Campaign",
			filters={
				"koc": self.name,
				"campaign_type": "Livestream",
				"start_time": ["<=", now],
				"end_time": [">=", now],
			},
			fields=["name", "campaign_name", "start_time", "end_time", "platforms"],
		)
