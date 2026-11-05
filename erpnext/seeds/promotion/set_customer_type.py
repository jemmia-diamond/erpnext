import frappe


def execute():
	"""Backfill for_new_customer / for_old_customer from the legacy title convention.

	Titles containing "mới" ("KH mới") apply to new customers only, titles containing
	"cũ" ("KH cũ") to old customers only, and every other promotion to both.
	Matching is done in Python because the DB collation is accent-insensitive
	(LIKE '%cũ%' would also match e.g. "cưới").
	"""
	for promotion in frappe.get_all("Promotion", fields=["name", "title"]):
		title = (promotion.title or "").lower()
		frappe.db.set_value(
			"Promotion",
			promotion.name,
			{
				"for_new_customer": 0 if "cũ" in title else 1,
				"for_old_customer": 0 if "mới" in title else 1,
			},
			update_modified=False,
		)
