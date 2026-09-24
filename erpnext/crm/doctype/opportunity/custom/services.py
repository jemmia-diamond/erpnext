import frappe
from frappe import _
from frappe.utils import getdate, nowdate, get_datetime, now_datetime


@frappe.whitelist(methods=["GET", "POST"])
def get_todo_opportunities(pancake_id=None, employee_email=None, status_filter="all"):
	"""
	Fetch active (not Done / Lost / Won / Closed) Opportunities for Salesaya Todo list.

	Args:
		pancake_id (str): Pancake User ID (e.g. from Salesaya extension).
		                  Resolved to Sales Person -> employee_email.
		employee_email (str): Direct user/employee email to filter by opportunity_owner.
		status_filter (str): "all" (Tất cả), "due_today" (Hạn hôm nay), or "overdue" (Quá hạn).

	Returns:
		dict: {
			"summary": {
				"total": int,
				"due_today": int,
				"overdue": int,
			},
			"items": list[dict]
		}
	"""
	# 1. Resolve sales owner email
	owner_email = resolve_owner_email(pancake_id, employee_email)
	if not owner_email:
		return {
			"summary": {"total": 0, "due_today": 0, "overdue": 0},
			"items": [],
		}

	# 2. Excluded closed/done statuses
	# Note: In ERPNext Opportunity, standard closed states are "Won", "Lost", "Closed"
	closed_statuses = ["Won", "Lost", "Closed"]

	# 3. Query active opportunities for this owner
	query = """
		SELECT 
			opp.name AS id,
			opp.title,
			opp.customer_name,
			opp.opportunity_from,
			opp.party_name,
			opp.phone,
			opp.contact_email,
			opp.status,
			opp.opportunity_owner,
			opp.note_count,
			opp.creation,
			opp.modified,
			opp.expected_delivery_date,
			opp.last_customer_message_at,
			opp.last_sales_message_at,
			l.first_reach_at AS lead_first_reach_at,
			l.image AS lead_image,
			con.pancake_page_id,
			con.pancake_conversation_id
		FROM `tabOpportunity` opp
		LEFT JOIN `tabLead` l ON (opp.opportunity_from = 'Lead' AND opp.party_name = l.name)
		LEFT JOIN `tabDynamic Link` dl ON (
			(dl.link_doctype = opp.opportunity_from AND dl.link_name = opp.party_name AND dl.parenttype = 'Contact')
			OR (opp.opportunity_from = 'Lead' AND dl.link_doctype = 'Lead' AND dl.link_name = opp.party_name AND dl.parenttype = 'Contact')
		)
		LEFT JOIN `tabContact` con ON con.name = dl.parent
		WHERE opp.opportunity_owner = %(owner)s
		  AND (opp.status NOT IN %(closed_statuses)s OR opp.status IS NULL)
		ORDER BY opp.creation DESC
	"""

	rows = frappe.db.sql(
		query,
		{
			"owner": owner_email,
			"closed_statuses": tuple(closed_statuses),
		},
		as_dict=True,
	)

	today = getdate(nowdate())

	total_count = 0
	due_today_count = 0
	overdue_count = 0
	items = []

	for r in rows:
		# Calculate distinct note dates if note_count is not backfilled yet
		note_cnt = r.get("note_count")
		if note_cnt is None:
			note_cnt = get_distinct_note_days(r["id"])

		created_date = getdate(r["creation"]) if r.get("creation") else today
		first_reach_date = (
			getdate(r["lead_first_reach_at"])
			if r.get("lead_first_reach_at")
			else created_date
		)

		# 7-day deadline from creation / first reach
		deadline_date = frappe.utils.add_days(first_reach_date, 7)
		days_left = (deadline_date - today).days

		if days_left == 0:
			deadline_label = "Hạn hôm nay"
			deadline_type = "due_today"
			due_today_count += 1
		elif days_left > 0:
			deadline_label = f"Còn {days_left} ngày"
			deadline_type = "active"
		else:
			overdue_days = abs(days_left)
			deadline_label = f"Quá {overdue_days} ngày"
			deadline_type = "overdue"
			overdue_count += 1

		total_count += 1

		# Filter if requested by status_filter
		if status_filter == "due_today" and deadline_type != "due_today":
			continue
		elif status_filter == "overdue" and deadline_type != "overdue":
			continue

		# Name fallback
		display_name = r.get("customer_name") or r.get("title") or r.get("party_name") or r.get("id")

		# Build Pancake URL if conversation_id and page_id are available
		pancake_page_id = r.get("pancake_page_id")
		pancake_conversation_id = r.get("pancake_conversation_id")
		pancake_url = None
		if pancake_page_id and pancake_conversation_id:
			pancake_url = f"https://pancake.vn/{pancake_page_id}?c_id={pancake_conversation_id}"

		items.append({
			"id": r["id"],
			"name": display_name,
			"title": r.get("title"),
			"customer_name": r.get("customer_name"),
			"party_name": r.get("party_name"),
			"opportunity_from": r.get("opportunity_from"),
			"phone": r.get("phone"),
			"status": r.get("status"),
			"note_count": note_cnt,
			"note_target": 3,
			"note_progress": f"{note_cnt}/3 lần",
			"image": r.get("lead_image"),
			"pancake_page_id": pancake_page_id,
			"pancake_conversation_id": pancake_conversation_id,
			"pancake_url": pancake_url,
			"creation": r.get("creation").strftime("%Y-%m-%d %H:%M:%S") if r.get("creation") else None,
			"first_reach_at": r.get("lead_first_reach_at").strftime("%Y-%m-%d %H:%M:%S") if r.get("lead_first_reach_at") else None,
			"deadline_date": str(deadline_date),
			"days_left": days_left,
			"deadline_label": deadline_label,
			"deadline_type": deadline_type,
		})

	return {
		"summary": {
			"total": total_count,
			"due_today": due_today_count,
			"overdue": overdue_count,
		},
		"items": items,
	}


def resolve_owner_email(pancake_id=None, employee_email=None):
	"""Resolve Pancake ID or Employee Email to the Opportunity Owner User ID/Email."""
	if employee_email:
		return str(employee_email).strip()

	if not pancake_id:
		return None

	pancake_id = str(pancake_id).strip()

	# 1. Look up in Sales Person by pancake_id
	sp = frappe.db.get_value(
		"Sales Person",
		{"pancake_id": pancake_id, "enabled": 1},
		["employee_email", "name"],
		as_dict=True,
	)
	if not sp:
		# Check without enabled filter
		sp = frappe.db.get_value(
			"Sales Person",
			{"pancake_id": pancake_id},
			["employee_email", "name"],
			as_dict=True,
		)

	if sp and sp.get("employee_email"):
		return sp["employee_email"]

	# 2. Look up in User doctype directly (if User has pancake_id field)
	if frappe.db.has_column("User", "pancake_id"):
		user_email = frappe.db.get_value("User", {"pancake_id": pancake_id, "enabled": 1}, "name")
		if user_email:
			return user_email

	return None


def get_distinct_note_days(opportunity_name):
	"""
	Count distinct days on which CRM Notes were added for an Opportunity.
	Multiple notes added on the same day count as 1.
	"""
	dates = frappe.db.sql(
		"""
		SELECT DISTINCT DATE(added_on) AS note_date
		FROM `tabCRM Note`
		WHERE parent = %(parent)s
		  AND parenttype = 'Opportunity'
		  AND added_on IS NOT NULL
		""",
		{"parent": opportunity_name},
		as_dict=True,
	)
	return len(dates)
