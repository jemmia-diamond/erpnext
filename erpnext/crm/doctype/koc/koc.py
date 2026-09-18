# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime


class KOC(Document):
	def validate(self):
		self.clean_slugs()
		if not self.attribution_window_days or self.attribution_window_days <= 0:
			self.attribution_window_days = 30
		self.sync_default_commission_plan()
		self.sort_commission_plans()
		self.render_commission_plans_json()

	def before_save(self):
		self.render_commission_plans_json()

	def render_commission_plans_json(self):
		"""Serialize commission_plans child table into commission_plans_json field."""
		data = []
		if getattr(self, "commission_plans", None):
			for plan in self.commission_plans:
				data.append({
					"from_date": str(plan.from_date) if plan.from_date else None,
					"commission_rate": float(plan.commission_rate or 0),
					"notes": plan.notes or "",
				})
		self.commission_plans_json = frappe.as_json(data)

	def sync_default_commission_plan(self):
		"""
		1. If KOC has default commission_rate set but no tracking rows in commission_plans,
		   automatically seed the first row with referral_valid_from (or now) and commission_rate.
		2. If existing KOC and commission_rate or referral_valid_from changed,
		   automatically append a new row to tracking table.
		"""
		if self.commission_rate and not self.get("commission_plans"):
			valid_from = self.referral_valid_from or frappe.utils.now_datetime()
			self.append(
				"commission_plans",
				{
					"from_date": valid_from,
					"commission_rate": self.commission_rate,
					"notes": "Initial default rate",
				},
			)
		elif not self.is_new() and self.has_value_changed("commission_rate"):
			valid_from = self.referral_valid_from or frappe.utils.now_datetime()
			self.append(
				"commission_plans",
				{
					"from_date": valid_from,
					"commission_rate": self.commission_rate,
					"notes": "Updated default rate",
				},
			)

	def clean_slugs(self):
		"""Normalize slugs to comma-separated lowercase strings without extra whitespace."""
		if self.slugs:
			slug_list = [s.strip().lower() for s in self.slugs.replace("\n", ",").split(",") if s.strip()]
			seen = set()
			unique_slugs = [s for s in slug_list if not (s in seen or seen.add(s))]
			self.slugs = ", ".join(unique_slugs)

	def sort_commission_plans(self):
		"""Sort commission plans chronologically by from_date descending."""
		if getattr(self, "commission_plans", None):
			self.commission_plans = sorted(
				self.commission_plans,
				key=lambda p: get_datetime(p.from_date) if p.from_date else get_datetime("1970-01-01"),
				reverse=True,
			)

	def get_commission_rate(self, target_date=None):
		"""
		Resolve effective commission rate for a given date/datetime.
		Searches commission_plans timeline first (from_date <= target_date).
		Falls back to self.commission_rate if no matching plan exists.
		"""
		if not target_date:
			target_date = frappe.utils.now_datetime()
		else:
			target_date = get_datetime(target_date)

		if getattr(self, "commission_plans", None):
			sorted_plans = sorted(self.commission_plans,
				key=lambda p: get_datetime(p.from_date) if p.from_date else get_datetime("1970-01-01"),
				reverse=True,
			)
			for plan in sorted_plans:
				if plan.from_date and get_datetime(plan.from_date) <= target_date:
					return float(plan.commission_rate or 0)

		return float(self.commission_rate or 0)

	def get_active_campaigns(self):
		"""Return all ongoing livestream campaigns where this KOC participates."""
		now = frappe.utils.now_datetime()
		campaign_names = frappe.get_all(
			"Campaign KOC",
			filters={"koc": self.name},
			pluck="parent",
		)
		if not campaign_names:
			return []

		return frappe.get_all(
			"Campaign",
			filters={
				"name": ["in", list(set(campaign_names))],
				"campaign_type": "Livestream",
				"start_time": ["<=", now],
				"end_time": [">=", now],
			},
			fields=["name", "campaign_name", "start_time", "end_time", "platforms"],
		)
