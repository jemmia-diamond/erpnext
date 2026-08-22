import json
import re
import time
from typing import TYPE_CHECKING, Any, cast

import frappe
import pymysql
from frappe import _
from frappe.automation.doctype.assignment_rule.assignment_rule import apply
from frappe.utils import get_datetime, sbool, validate_phone_number
from frappe.www.contact import get_contacts_by_conversation_id
from pymysql.constants import ER, FIELD_TYPE
from pymysql.converters import conversions, escape_string

from erpnext.config.config import config
from erpnext.crm.doctype.crm_settings.crm_settings_service import get_crm_settings
from erpnext.crm.doctype.lead.lead import Lead
from erpnext.crm.doctype.lead.lead_dao import get_lead_by_name, get_lead_name_by_conversation_id
from erpnext.crm.doctype.lead_budget.lead_budget_dao import find_range_budget
from erpnext.crm.doctype.lead_demand.lead_demand_dao import get_lead_purpose
from erpnext.crm.doctype.lead_product.lead_product_dao import create_lead_product, get_lead_product
from erpnext.crm.doctype.opportunity.custom.opportunity_custom import move_to_opportunity
from erpnext.utilities.phone_utils import (
	get_phone_variants,
	is_valid_phone_number,
	normalize_to_standard_format,
	search_doc_by_phone,
)

if TYPE_CHECKING:
	from frappe.model.document import Document


def is_non_empty(value: str | None) -> bool:
	return bool(value and value.strip())


def truncate_string(value: str | None, max_length: int = 140) -> str | None:
	if value and isinstance(value, str) and len(value) > max_length:
		return value[:max_length]
	return value


def is_valid_lead_name(name_val: str | None) -> bool:
	name_str = (name_val or "").strip()
	placeholder_names = [None, "Chưa rõ", "Unknown", ""]
	if name_str in placeholder_names:
		return False

	# If string ONLY contains digits, spaces, and phone symbols -> invalid name
	if not re.search(r"[^\d\s\+\-\(\)]", name_str):
		return False

	return True


def normalize_phone_number(phone: str | None) -> str | None:
	"""Normalize phone number to standard format (country code + number, no prefix).
	Examples:
	        +84 955 555 555 -> 84955555555
	        0955555555 -> 84955555555
	        84955555555 -> 84955555555
	        840932344355 -> 84932344355 (edge case: removes extra 0)
	        +1 (555)-000-4321 -> 15550004321
	        +86 138 0013 8000 -> 8613800138000
	"""
	if not phone:
		return None
	res = normalize_to_standard_format(phone)
	return res if res else None


@frappe.whitelist(methods=["POST", "PUT"])
def insert_lead_by_batch(docs=None):
	"""Insert multiple lead

	:param docs: JSON or list of dict objects to be inserted in one request"""

	crm_settings = get_crm_settings()
	if not crm_settings.get("enable_auto_lead_insert", 1):
		frappe.throw("currently backfilling")

	if not docs:
		return []

	if len(docs) > 200:
		frappe.throw(_("Only 200 inserts allowed in one request"))

	result: list[dict[str, Any]] = []
	for doc in docs:
		doc = doc.copy()
		pancake_data = doc.get("pancake_data", {})
		conversation_id = pancake_data.get("conversation_id")

		if not is_non_empty(conversation_id):
			frappe.logger().warning("insert_lead_by_batch: missing conversation_id", exc_info=False)
			result.append({"name": None, "conversation_id": conversation_id})
			continue

		try:
			inserted_doc = insert_lead(doc)
			if inserted_doc:
				result.append({"name": inserted_doc.name, "conversation_id": conversation_id})
			else:
				result.append({"name": None, "conversation_id": conversation_id})
		except Exception:
			result.append({"name": None, "conversation_id": conversation_id})
	return result


def insert_lead(doc) -> "Document | None":
	"""Inserts document and returns parent document object with appended child document
	if `doc` is child document else returns the inserted document object

	:param doc: doc to insert (dict)"""

	doc = frappe._dict(doc)

	for field in ["lead_name", "first_name", "last_name", "middle_name"]:
		if field in doc:
			doc[field] = truncate_string(doc.get(field))

	doctype = doc.get("doctype")
	if doctype and frappe.is_table(doctype):
		parenttype = cast(str, doc.get("parenttype"))
		parent = cast(str, doc.get("parent"))
		parentfield = cast(str, doc.get("parentfield"))
		if not (parenttype and parent and parentfield):
			frappe.throw(_("Parenttype, Parent and Parentfield are required to insert a child record"))

		# inserting a child record
		parent_doc = frappe.get_doc(parenttype, parent)
		parent_doc.append(parentfield, doc)
		parent_doc.save()
		return parent_doc

	is_valid_phone = False
	pancake_phone = normalize_phone_number(doc.get("phone"))
	doc["phone"] = pancake_phone
	if pancake_phone:
		is_valid_phone = validate_phone_number(pancake_phone)
		if is_valid_phone is False:
			doc["phone"] = None
			pancake_phone = None

	pancake_data = doc.get("pancake_data", {})

	pancake_list_tags = doc.get("pancake_tags", [])
	if pancake_list_tags:
		pancake_list_tags = [transform_price_label(tag) for tag in pancake_list_tags]

	page_id = pancake_data.get("page_id")
	conversation_id = pancake_data.get("conversation_id")

	if is_non_empty(conversation_id):
		existing_lead_name = get_lead_name_by_conversation_id(conversation_id)
		if existing_lead_name:
			existing_doc = cast("Lead", frappe.get_doc("Lead", existing_lead_name))
			existing_doc.link_to_contacts(pancake_data=pancake_data)
			return existing_doc

	# Check if lead exists by phone
	if is_valid_phone and is_non_empty(pancake_phone):
		existing_lead_name = frappe.db.get_value("Lead", {"phone": pancake_phone}, "name")
		if existing_lead_name:
			existing_doc = cast("Lead", frappe.get_doc("Lead", existing_lead_name))
			if conversation_id and page_id:
				existing_doc.link_to_contacts(pancake_data=pancake_data)
			return existing_doc

	frappe_doc = cast("Lead", frappe.get_doc(doc))
	try:
		"""
		Insert a new Lead
		"""
		frappe_doc = frappe_doc.insert()

		if pancake_list_tags:
			for tag in pancake_list_tags:
				frappe_doc.add_tag(tag)
				if str(tag).strip().lower() == "spam":
					frappe_doc.db_set("status", "Spam")

		# only exist when migrate from pancake
		# lead reach at before 2025/06/15 21:00:00
		first_reach = frappe_doc.first_reach_at
		if first_reach:
			reach_dt = get_datetime(cast(Any, first_reach))
			cutoff_dt = get_datetime(config.DATE_ASSIGN_LEAD_OWNER)
			if reach_dt and cutoff_dt and reach_dt < cutoff_dt:
				try:
					if frappe_doc.name:
						create_lead_todo(frappe_doc.name, frappe_doc.lead_owner)
				except Exception as e:
					frappe.log_error(e)

		return frappe_doc
	except Exception:
		try:
			doc_doctype = frappe_doc.doctype
			doc_name = frappe_doc.name
			if doc_doctype and doc_name:
				existing_doc = frappe.get_doc(doc_doctype, doc_name)
				if existing_doc:
					return existing_doc
			return None
		except Exception:
			return None


@frappe.whitelist(methods=["PUT", "PATCH"])
def backfill_lead_info(docs):
	"""Bulk update leads"""
	if isinstance(docs, str):
		docs = json.loads(docs)

	failed_docs = []
	try:
		# Prepare parts for the dynamic SQL query
		name_case_when_clauses = []
		phone_case_when_clauses = []
		ids_to_update = []
		sql_params_name = []  # Separate list for first_name parameters
		sql_params_phone = []  # Separate list for phone parameters

		for doc in docs:
			lead_id = doc.get("docname")
			new_name = truncate_string(doc.get("new_name"))
			new_phone = doc.get("new_phone")

			if not lead_id:
				failed_docs.append(
					{"doc": doc, "exc": "Missing 'docname' (lead ID). Skipping this document."}
				)
				continue  # Skip this document if docname is missing

			ids_to_update.append(lead_id)

			# Build CASE WHEN clauses for first_name with nested conditions
			if is_non_empty(new_name):  # Only add clause if new_name is not empty
				name_case_when_clauses.append(
					"""
                    WHEN name = %s THEN
                        CASE
                            WHEN first_name IS NULL OR first_name = '' OR first_name = 'Chưa rõ' THEN %s
                            ELSE first_name
                        END
                """
				)
				# Parameters for this clause: lead_id (for outer WHEN) and new_name (for inner THEN)
				sql_params_name.extend([lead_id, new_name])

			# Build CASE WHEN clauses for phone with nested conditions
			if is_non_empty(new_phone):  # Only add clause if new_phone is not empty
				phone_case_when_clauses.append(
					"""
                    WHEN name = %s THEN
                        CASE
                            WHEN phone IS NULL OR phone = '' THEN %s
                            ELSE phone
                        END
                """
				)
				# Parameters for this clause: lead_id (for outer WHEN) and new_phone (for inner THEN)
				sql_params_phone.extend([lead_id, new_phone])

		# If no valid documents were processed to build clauses, return
		if not ids_to_update:
			return {"failed_docs": failed_docs}
		# Add all lead IDs for the WHERE IN clause at the very end of the parameters list
		ids_clause_placeholders = ", ".join(["%s"] * len(ids_to_update))

		# Construct SQL query dynamically
		sql_query = f"""
            UPDATE `tabLead`
            SET
                first_name = CASE
                    {' '.join(name_case_when_clauses)}
                    ELSE first_name -- Fallback: if name matches but no WHEN clause matched, keep current first_name
                END,
                phone = CASE
                    {' '.join(phone_case_when_clauses)}
                    ELSE phone -- Fallback: if name matches but no WHEN clause matched, keep current phone
                END
            WHERE name IN ({ids_clause_placeholders})
        """
		sql_params = sql_params_name + sql_params_phone + ids_to_update

		frappe.db.sql(sql_query, tuple(sql_params))

	except Exception:
		for doc in docs:
			failed_docs.append({"doc": doc, "exc": frappe.utils.get_traceback()})

	return {"failed_docs": failed_docs}


@frappe.whitelist(methods=["POST", "PUT"])
def update_lead_by_batch(docs):
	"""Bulk update leads

	:param docs: JSON list of documents to be updated remotely. Each document must have `docname` property"""

	crm_settings = get_crm_settings()
	if not crm_settings.get("enable_auto_lead_insert", 1):
		frappe.throw("currently backfilling")

	if isinstance(docs, str):
		docs = json.loads(docs)
	failed_docs = []
	results = []
	for doc in docs:
		doc = doc.copy()
		doc.pop("flags", None)

		for field in ["lead_name", "first_name", "last_name", "middle_name"]:
			if field in doc:
				doc[field] = truncate_string(doc.get(field))

		pancake_data = doc.get("pancake_data", {})
		try:
			pancake_phone = normalize_phone_number(doc.get("phone"))
			if pancake_phone is not None:
				doc["phone"] = pancake_phone
				is_valid_phone = validate_phone_number(pancake_phone)
				if is_valid_phone is False:
					doc["phone"] = None
					pancake_phone = None
			else:
				doc.pop("phone", None)

			existing_doc: "Lead" | None = None
			try:
				existing_doc = cast("Lead", frappe.get_doc(doc["doctype"], doc["docname"]))
			except (frappe.DoesNotExistError, Exception):
				conversation_id = pancake_data.get("conversation_id")
				lead_name = (
					get_lead_name_by_conversation_id(conversation_id)
					if is_non_empty(conversation_id)
					else None
				)

				if lead_name:
					existing_doc = cast("Lead", frappe.get_doc(doc["doctype"], lead_name))
				else:
					doc.pop("docname", None)
					existing_doc = cast("Lead", insert_lead(doc))

			if not existing_doc:
				raise ValueError("Failed to retrieve or create lead document")

			# exist phone not update
			if existing_doc.phone and existing_doc.phone != "":
				doc["phone"] = normalize_phone_number(existing_doc.phone)

			# Check if the new phone number already exists in another lead
			new_phone = doc.get("phone")
			if is_non_empty(new_phone):
				existing_doc = handle_duplicate_and_merge(existing_doc, new_phone)

			if is_valid_lead_name(existing_doc.lead_name):
				doc["first_name"] = existing_doc.lead_name
				doc["lead_name"] = existing_doc.lead_name

			if existing_doc.lead_owner:
				doc["lead_owner"] = existing_doc.lead_owner

			existing_doc.update(doc)
			existing_doc.save(ignore_permissions=True)
			frappe.db.commit()

			existing_doc.link_to_contacts(pancake_data)

			try:
				pancake_list_tags = doc.get("pancake_tags", [])
				if pancake_list_tags:
					pancake_list_tags = [transform_price_label(tag) for tag in pancake_list_tags]
					for tag in pancake_list_tags:
						existing_doc.add_tag(tag)
			except Exception:
				pass

			results.append(
				{"conversation_id": pancake_data.get("conversation_id"), "name": existing_doc.name}
			)

		except Exception:
			results.append({"conversation_id": pancake_data.get("conversation_id"), "name": None})
			failed_docs.append({"doc": doc, "exc": frappe.utils.get_traceback()})

	return {"results": results, "failed_docs": failed_docs}


def handle_duplicate_and_merge(existing_doc: "Lead", new_phone: str) -> "Lead":
	"""
	Check if new_phone belongs to another lead.
	If so, keep the oldest lead (by first_reach_at), merge contacts and
	downstream documents, and delete the duplicate.
	Returns the 'master' document that survived.
	"""
	if not is_non_empty(new_phone):
		return existing_doc

	# Do not merge on invalid or dummy phone numbers (e.g., "0")
	if not is_valid_phone_number(new_phone):
		return existing_doc

	normalized_phone = normalize_phone_number(new_phone)
	if not normalized_phone:
		return existing_doc

	conflicting_lead = frappe.db.get_value("Lead", {"phone": normalized_phone}, "name")

	if not conflicting_lead or conflicting_lead == existing_doc.name:
		return existing_doc

	conflicting_doc = cast("Lead", frappe.get_doc("Lead", conflicting_lead))

	# Determine which lead is older (Master) and which is newer (Loser)
	is_existing_older = False
	if existing_doc.first_reach_at and conflicting_doc.first_reach_at:
		existing_reach_dt = get_datetime(cast(Any, existing_doc.first_reach_at))
		conflicting_reach_dt = get_datetime(cast(Any, conflicting_doc.first_reach_at))
		if existing_reach_dt and conflicting_reach_dt and existing_reach_dt < conflicting_reach_dt:
			is_existing_older = True
	elif existing_doc.first_reach_at:  # conflicting has no date
		is_existing_older = True

	if is_existing_older:
		master_doc = existing_doc
		loser_doc = conflicting_doc
	else:
		master_doc = conflicting_doc
		loser_doc = existing_doc

	try:
		frappe.db.savepoint("lead_merge")
		if loser_doc.name and master_doc.name:
			# Re-link loser's contacts and addresses to master
			_relink_dynamic_links(loser_doc.name, master_doc.name)

			# Re-link downstream docs to master
			_relink_downstream_docs(loser_doc.name, master_doc.name)

			# Transfer field values from loser to master
			_transfer_lead_fields(master_doc, loser_doc)

			# Merge system/virtual fields
			_merge_system_fields(master_doc, loser_doc)

			# Transfer child tables and related docs
			_transfer_child_tables(master_doc, loser_doc)
			transfer_lead_todos(loser_doc.name, master_doc.name)

			# Delete loser and finalize master
			frappe.delete_doc("Lead", loser_doc.name, ignore_permissions=True, force=True)
			master_doc.set_first_lead_source()

	except Exception as e:
		frappe.db.rollback(save_point="lead_merge")
		frappe.log_error(
			f"Failed to merge lead {loser_doc.name} into {master_doc.name}: {e!s}.", "Lead Merge Error"
		)
		raise

	return master_doc


@frappe.whitelist(methods=["POST"])
def merge_leads_by_phone(phone, first_reach_at=None, current_lead_name=None):
	"""
	API for frontend to trigger merge for a specific phone number.
	Input: phone, first_reach_at (optional), current_lead_name (optional)
	Returns the Master Lead name.
	"""

	crm_settings = get_crm_settings()
	if not crm_settings.get("enable_lead_phone_update_or_merge", 1):
		frappe.local.response["http_status_code"] = 400
		return {"status": "disabled", "message": "currently disabled"}

	if not phone:
		frappe.throw("Phone is required")

	normalized = normalize_phone_number(phone)
	if not normalized:
		frappe.throw("Invalid phone number")

	variants = get_phone_variants(phone)
	if not variants:
		variants = [normalized]

	leads_data = frappe.get_all(
		"Lead",
		or_filters={"phone": ["in", variants], "mobile_no": ["in", variants]},
		fields=["name", "first_reach_at", "creation"],
	)

	# Ensure current_lead_name is in the list to be considered
	if current_lead_name and frappe.db.exists("Lead", current_lead_name):
		if not any(l.name == current_lead_name for l in leads_data):
			current_lead_data = frappe.get_all(
				"Lead", filters={"name": current_lead_name}, fields=["name", "first_reach_at", "creation"]
			)
			if current_lead_data:
				leads_data.append(current_lead_data[0])

	if not leads_data:
		return None

	# Sort leads by first_reach_at ASC, creation ASC in Python
	def sort_key(l):
		# Use a far future date if first_reach_at is None
		reach = l.first_reach_at or get_datetime("2999-01-01")
		creation = l.creation or get_datetime("2999-01-01")
		return (reach, creation)

	leads_data.sort(key=sort_key)

	# If there's only one lead (which could be the current_lead_name), just update it
	if len(leads_data) == 1:
		master_name = leads_data[0].name
		doc = cast("Lead", frappe.get_doc("Lead", master_name))
		changed = False
		if doc.phone != normalized:
			doc.phone = normalized
			changed = True

		if changed:
			doc.flags.ignore_permissions = True
			doc.save()
			frappe.db.commit()

		return master_name

	# Multiple leads found
	master_name = leads_data[0].name
	master_doc = cast("Lead", frappe.get_doc("Lead", master_name))

	if master_doc.phone != normalized:
		master_doc.phone = normalized

	loser_leads = [l.name for l in leads_data[1:]]
	for loser_name in loser_leads:
		try:
			loser_doc = cast("Lead", frappe.get_doc("Lead", loser_name))
			frappe.db.savepoint("api_merge")
			if loser_doc.name and master_doc.name:
				_relink_dynamic_links(loser_doc.name, master_doc.name)
				_relink_downstream_docs(loser_doc.name, master_doc.name)
				_transfer_lead_fields(master_doc, loser_doc)
				_merge_system_fields(master_doc, loser_doc)
				_transfer_child_tables(master_doc, loser_doc)
				transfer_lead_todos(loser_doc.name, master_doc.name)
				frappe.delete_doc("Lead", loser_doc.name, ignore_permissions=True, force=True)
				frappe.db.commit()
		except Exception as e:
			frappe.db.rollback(save_point="api_merge")
			frappe.log_error(f"API Merge failed {loser_name} into {master_name}: {e!s}", "Lead Merge Error")

	master_doc.set_first_lead_source()
	master_doc.save(ignore_permissions=True)
	frappe.db.commit()

	return master_doc.name


@frappe.whitelist()
def bulk_merge_duplicate_leads(enqueue=True):
	"""
	Enqueues background job to merge duplicate leads grouped by last 8 digits of phone.
	"""
	frappe.only_for("System Manager")

	duplicate_phones = frappe.db.sql(
		"""
		SELECT RIGHT(phone, 8) as phone_suffix
		FROM `tabLead`
		WHERE phone IS NOT NULL AND phone != ''
		GROUP BY RIGHT(phone, 8)
		HAVING COUNT(*) > 1
	""",
		as_dict=True,
	)

	if str(enqueue).lower() in ["true", "1", "yes"]:
		frappe.enqueue(
			"erpnext.crm.doctype.lead.lead_methods.process_bulk_merge",
			duplicate_phones=duplicate_phones,
			queue="long",
		)
		return f"Enqueued bulk merge for {len(duplicate_phones)} duplicate groups."
	else:
		process_bulk_merge(duplicate_phones)
		return f"Processed {len(duplicate_phones)} duplicate groups directly."


def process_bulk_merge(duplicate_phones):
	"""
	Processes bulk merge of leads.
	Master = oldest first_reach_at (or creation).
	Losers = merged into master.
	"""
	for row in duplicate_phones:
		suffix = row.phone_suffix
		leads = frappe.db.sql(
			"""
			SELECT name
			FROM `tabLead`
			WHERE RIGHT(phone, 8) = %s
			ORDER BY IFNULL(first_reach_at, '2999-01-01') ASC, creation ASC
		""",
			(suffix,),
			as_dict=True,
		)

		if len(leads) <= 1:
			continue

		master_lead = leads[0].name
		loser_leads = [l.name for l in leads[1:]]
		master_doc = cast("Lead", frappe.get_doc("Lead", master_lead))

		for loser_name in loser_leads:
			try:
				loser_doc = cast("Lead", frappe.get_doc("Lead", loser_name))
				frappe.db.savepoint("lead_merge")
				if loser_doc.name and master_doc.name:
					_relink_dynamic_links(loser_doc.name, master_doc.name)
					_relink_downstream_docs(loser_doc.name, master_doc.name)
					_transfer_lead_fields(master_doc, loser_doc)
					_merge_system_fields(master_doc, loser_doc)
					_transfer_child_tables(master_doc, loser_doc)
					transfer_lead_todos(loser_doc.name, master_doc.name)
					frappe.delete_doc("Lead", loser_doc.name, ignore_permissions=True, force=True)
					frappe.db.commit()
			except Exception as e:
				frappe.db.rollback(save_point="lead_merge")
				frappe.log_error(
					f"Bulk Merge: Failed {loser_name} into {master_lead}: {e!s}", "Lead Merge Error"
				)

		try:
			master_doc.set_first_lead_source()
			master_doc.save(ignore_permissions=True)
			frappe.db.commit()
		except Exception as e:
			frappe.log_error(f"Bulk Merge: Failed save master {master_lead}: {e!s}", "Lead Merge Error")


@frappe.whitelist()
def fix_unnormalized_leads(enqueue=False):
	leads = frappe.db.sql(
		"""
		SELECT name, phone
		FROM `tabLead`
		WHERE phone LIKE '+%%' or phone like '0%%'
	""",
		as_dict=True,
	)

	if str(enqueue).lower() in ["true", "1", "yes"]:
		frappe.enqueue(
			"erpnext.crm.doctype.lead.lead_methods.process_fix_unnormalized",
			leads=leads,
			queue="long",
			timeout=3600,
		)
		return f"Enqueued fix for {len(leads)} leads."
	else:
		process_fix_unnormalized(leads)
		return f"Processed {len(leads)} leads directly."


def process_fix_unnormalized(leads):
	for row in leads:
		lead_name = row.name
		old_phone = row.phone

		normalized = normalize_to_standard_format(old_phone)
		if not normalized or normalized == old_phone:
			continue

		try:
			doc = cast("Lead", frappe.get_doc("Lead", lead_name))
			doc.phone = normalized
			doc.save(ignore_permissions=True)
			frappe.db.commit()

		except Exception as e:
			frappe.db.rollback()
			err_str = str(e)

			if (
				isinstance(e, frappe.UniqueValidationError | pymysql.err.IntegrityError)
				or "must be unique" in err_str
				or "already used in" in err_str
			):
				# Catch unique error -> Find conflicting lead
				conflicting_lead = frappe.db.get_value("Lead", {"phone": normalized}, "name")
				if not conflicting_lead or conflicting_lead == lead_name:
					frappe.log_error(f"Fix failed for {lead_name}, not duplicate: {e!s}", "Lead Fix Error")
					continue

				# Conflict exist -> Merge
				master_doc = cast("Lead", frappe.get_doc("Lead", conflicting_lead))
				loser_doc = cast("Lead", frappe.get_doc("Lead", lead_name))

				# Pick Master by first_reach_at
				master_older = False
				if master_doc.first_reach_at and loser_doc.first_reach_at:
					master_reach_dt = get_datetime(cast(Any, master_doc.first_reach_at))
					loser_reach_dt = get_datetime(cast(Any, loser_doc.first_reach_at))
					if master_reach_dt and loser_reach_dt and master_reach_dt < loser_reach_dt:
						master_older = True
				elif master_doc.first_reach_at:
					master_older = True
				elif not loser_doc.first_reach_at:
					# Both no reach date -> Use creation
					if cast(Any, master_doc.creation) < cast(Any, loser_doc.creation):
						master_older = True

				if not master_older:
					# Swap roles
					master_doc, loser_doc = loser_doc, master_doc
				try:
					frappe.db.savepoint("fix_merge")
					if loser_doc.name and master_doc.name:
						_relink_dynamic_links(loser_doc.name, master_doc.name)
						_relink_downstream_docs(loser_doc.name, master_doc.name)
						_transfer_lead_fields(master_doc, loser_doc)
						_merge_system_fields(master_doc, loser_doc)
						_transfer_child_tables(master_doc, loser_doc)
						transfer_lead_todos(loser_doc.name, master_doc.name)

						frappe.delete_doc("Lead", loser_doc.name, ignore_permissions=True, force=True)

						master_doc.set_first_lead_source()
						master_doc.save(ignore_permissions=True)
						frappe.db.commit()
				except Exception as merge_e:
					frappe.db.rollback(save_point="fix_merge")
					frappe.log_error(
						f"Fix Merge fail {loser_doc.name} into {master_doc.name}: {merge_e!s}",
						"Lead Merge Error",
					)
			else:
				frappe.log_error(f"Fix fail {lead_name}: {e!s}", "Lead Fix Error")


def _relink_dynamic_links(from_lead: str, to_lead: str):
	"""Re-link Contact and Address Dynamic Link records from one lead to another."""
	for doctype in ("Contact", "Address"):
		linked_docs = frappe.get_all(
			doctype,
			filters=[
				["Dynamic Link", "link_doctype", "=", "Lead"],
				["Dynamic Link", "link_name", "=", from_lead],
			],
			fields=["name"],
		)

		for doc in linked_docs:
			frappe.db.sql(
				"""
				UPDATE `tabDynamic Link`
				SET link_name = %s
				WHERE link_doctype = 'Lead' AND link_name = %s AND parent = %s
			""",
				(to_lead, from_lead, doc.name),
			)


def _relink_downstream_docs(from_lead: str, to_lead: str):
	"""Re-link all downstream documents, logs, and audits from one lead to another."""
	# Customers linked via lead_name
	frappe.db.sql(
		"""
		UPDATE `tabCustomer`
		SET lead_name = %s
		WHERE lead_name = %s
	""",
		(to_lead, from_lead),
	)

	# Appointments linked via lead
	frappe.db.sql(
		"""
		UPDATE `tabAppointment`
		SET `lead` = %s
		WHERE `lead` = %s
	""",
		(to_lead, from_lead),
	)

	# Communications referencing this lead
	frappe.db.sql(
		"""
		UPDATE `tabCommunication`
		SET reference_name = %s
		WHERE reference_doctype = 'Lead' AND reference_name = %s
	""",
		(to_lead, from_lead),
	)

	# File attachments
	frappe.db.sql(
		"""
		UPDATE `tabFile`
		SET attached_to_name = %s
		WHERE attached_to_doctype = 'Lead' AND attached_to_name = %s
	""",
		(to_lead, from_lead),
	)

	# Version Audit Trail
	frappe.db.sql(
		"""
		UPDATE `tabVersion`
		SET docname = %s
		WHERE ref_doctype = 'Lead' AND docname = %s
	""",
		(to_lead, from_lead),
	)

	# Comments timeline
	frappe.db.sql(
		"""
		UPDATE `tabComment`
		SET reference_name = %s
		WHERE reference_doctype = 'Lead' AND reference_name = %s
	""",
		(to_lead, from_lead),
	)


def _transfer_lead_fields(master_doc, loser_doc):
	"""Transfer enrichment and profile fields from loser to master where master lacks them."""
	fill_if_empty_fields = [
		"region",
		"province",
		"budget_lead",
		"purpose_lead",
		"expected_delivery_date",
		"email_id",
		"gender",
		"birth_date",
		"whatsapp_no",
		"image",
		"first_reach_at",
		"mobile_no",
		"source",
		"first_channel",
		"customer",
		"personal_id",
		"company_name",
		"company",
		"salutation",
		"utm_campaign",
		"utm_source",
		"utm_medium",
		"utm_content",
		"job_title",
		"territory",
		"stringee_data",
		"qualified_lead_date",
		"first_name",
		"middle_name",
		"last_name",
		"fax",
		"type",
		"market_segment",
		"industry",
		"request_type",
		"website",
		"unsubscribed",
		"blog_subscriber",
		"language",
		"no_of_employees",
		"phone_ext",
		"annual_revenue",
		"city",
		"state",
		"country",
		"address",
		"place_of_issuance",
		"date_of_issuance",
		"bank_name",
		"bank_branch",
		"account_number",
		"bank_province",
		"bank_district",
		"bank_ward",
		"tax_number",
		"ceo_name",
		"personal_tax_id",
		"proposed_budget",
		"website_from_data",
		"qualified_by",
		"qualified_on",
	]
	for field in fill_if_empty_fields:
		if not master_doc.get(field) and loser_doc.get(field):
			master_doc.set(field, loser_doc.get(field))

	# Transfer lead_owner. The default mail owner is considered unassigned.
	master_has_real_owner = master_doc.lead_owner and master_doc.lead_owner != config.DEFAULT_MAIL_OWNER
	loser_has_real_owner = loser_doc.lead_owner and loser_doc.lead_owner != config.DEFAULT_MAIL_OWNER
	if not master_has_real_owner and loser_has_real_owner:
		master_doc.lead_owner = loser_doc.lead_owner

	if not is_valid_lead_name(master_doc.get("lead_name")) and is_valid_lead_name(loser_doc.get("lead_name")):
		master_doc.lead_name = loser_doc.lead_name
		master_doc.first_name = loser_doc.first_name
		master_doc.middle_name = loser_doc.middle_name
		master_doc.last_name = loser_doc.last_name

	# Retain the most advanced lead stage between the two records.
	_STAGE_ORDER = {"Lead": 0, "Qualified Lead": 1, "Opportunity": 2, "Customer": 3}
	master_stage_rank = _STAGE_ORDER.get(master_doc.lead_stage, 0)
	loser_stage_rank = _STAGE_ORDER.get(loser_doc.lead_stage, 0)
	if loser_stage_rank > master_stage_rank:
		master_doc.lead_stage = loser_doc.lead_stage

	# Prioritize 'Qualified' status if present in either record.
	if loser_doc.qualification_status == "Qualified" and master_doc.qualification_status != "Qualified":
		master_doc.qualification_status = "Qualified"
		if loser_doc.qualified_by:
			master_doc.qualified_by = loser_doc.qualified_by
		if loser_doc.qualified_on:
			master_doc.qualified_on = loser_doc.qualified_on

	# Status has a default of "New" / "Lead", so if Master is untouched and Loser has progress, inherit it.
	if master_doc.status in ("Lead", "New") and loser_doc.status not in ("Lead", "New"):
		master_doc.status = loser_doc.status


def _merge_system_fields(master_doc, loser_doc):
	"""Merge virtual/system fields (_assign, _user_tags) that require direct DB writes."""
	_merge_assign(master_doc, loser_doc)
	_merge_tags(master_doc, loser_doc)


def _merge_assign(master_doc, loser_doc):
	"""Merge _assign JSON arrays from both leads (deduplicated)."""
	try:
		master_assign = json.loads(master_doc._assign or "[]")
	except (json.JSONDecodeError, TypeError):
		master_assign = []

	try:
		loser_assign = json.loads(loser_doc._assign or "[]")
	except (json.JSONDecodeError, TypeError):
		loser_assign = []

	combined_assign = master_assign.copy()
	for email in loser_assign:
		if email not in combined_assign:
			combined_assign.append(email)

	if combined_assign != master_assign:
		frappe.db.set_value("Lead", master_doc.name, "_assign", json.dumps(combined_assign))
		master_doc._assign = json.dumps(combined_assign)


def _merge_tags(master_doc, loser_doc):
	"""Merge _user_tags from loser to master."""
	master_tags = {t.strip() for t in (master_doc.get("_user_tags") or "").split(",") if t.strip()}
	loser_tags = {t.strip() for t in (loser_doc.get("_user_tags") or "").split(",") if t.strip()}

	combined_tags = master_tags.union(loser_tags)
	if combined_tags != master_tags:
		new_tags_str = "," + ",".join(combined_tags) if combined_tags else ""
		frappe.db.set_value("Lead", master_doc.name, "_user_tags", new_tags_str)
		master_doc._user_tags = new_tags_str


def _transfer_child_tables(master_doc, loser_doc):
	"""Transfer child table records (preferred products, notes) from loser to master."""
	# Preferred products (deduplicated)
	if loser_doc.get("preferred_product_type"):
		existing_prods = {item.product_type for item in master_doc.get("preferred_product_type", [])}
		for p in loser_doc.get("preferred_product_type", []):
			if p.product_type not in existing_prods:
				master_doc.append("preferred_product_type", {"product_type": p.product_type})

	# Notes (appended in memory to survive Frappe's child table sync)
	_transfer_notes(loser_doc.name, master_doc)


def _transfer_notes(from_lead: str, master_doc):
	"""Transfer notes from loser lead to master lead (in memory) and append an audit trail note."""
	# Append system audit trail note
	master_doc.append(
		"notes",
		{
			"note": f"System: Lead {from_lead} was identified as a duplicate and merged into this record.",
			"type": "System",
			"added_by": getattr(frappe.session, "user", "Administrator"),
			"added_on": frappe.utils.now_datetime(),
		},
	)

	loser_notes = frappe.get_all(
		"CRM Note",
		filters={"parent": from_lead, "parenttype": "Lead"},
		fields=["note", "added_by", "added_on", "notify_to", "type"],
	)

	for n in loser_notes:
		master_doc.append(
			"notes",
			{
				"note": f"[Merged from {from_lead}] {n.note}",
				"type": n.type or "Other",
				"added_by": n.added_by,
				"added_on": n.added_on,
				"notify_to": n.notify_to,
			},
		)


def transform_price_label(label: str) -> str:
	return label.replace("<", "dưới ").replace(">", "trên ").strip()


def get_lead_province(province: str):
	lead_province = None

	try:
		lead_province = frappe.get_doc("Province", cast(Any, {"province_name": province}))
	except Exception:
		return None
	return lead_province


@frappe.whitelist(methods=["POST"])
def update_lead_from_summary(data):
	if isinstance(data, str):
		data = frappe.parse_json(data)

	conversation_id = data.get("conversation_id")
	if not is_non_empty(conversation_id):
		frappe.logger().warning("update_lead_from_summary: missing conversation_id", exc_info=False)
		return

	lead_name = get_lead_name_by_conversation_id(conversation_id)
	if not lead_name:
		update_contact_summary_timestamp(conversation_id)
		return

	lead_doc = get_lead_by_name(lead_name)
	if not lead_doc:
		update_contact_summary_timestamp(conversation_id)
		return

	lead = cast("Lead", lead_doc)

	budget_to = data.get("budget_to")
	budget_from = None if budget_to else data.get("budget_from")
	budget_name = data.get("budget_name")
	purpose = data.get("purpose")
	product_names = data.get("interested_products", [])
	province = data.get("province")
	expected_receiving_date = data.get("expected_receiving_date")

	new_lead_budget = find_range_budget(budget_name, budget_from, budget_to)
	new_lead_purpose = get_lead_purpose(purpose)
	new_lead_province = get_lead_province(province)

	move_to_opportunity_flag = get_crm_settings().get("move_to_opportunity", 0)
	products = []
	opp_products = []
	if product_names:
		for product_name in product_names:
			lead_product = get_lead_product(product_name)
			if not lead_product:
				lead_product = create_lead_product(product_name)
			if lead_product:
				if move_to_opportunity_flag:
					opp_products.append(lead_product)
				else:
					products.append(lead_product)

	opp_purpose = new_lead_purpose.name if new_lead_purpose and move_to_opportunity_flag else None
	opp_date = expected_receiving_date if expected_receiving_date and move_to_opportunity_flag else None

	if opp_products or opp_purpose or opp_date:
		phone = lead.get("phone")
		move_to_opportunity(
			phone, products=opp_products, purpose_lead=opp_purpose, expected_delivery_date=opp_date
		)
	max_retries = 3
	for attempt in range(max_retries):
		try:
			if attempt > 0:
				lead.reload()

			if new_lead_budget:
				lead.budget_lead = new_lead_budget.name
			if new_lead_purpose and not move_to_opportunity_flag:
				lead.purpose_lead = new_lead_purpose.name
			if expected_receiving_date and not move_to_opportunity_flag:
				lead.expected_delivery_date = expected_receiving_date
			if new_lead_province:
				lead.province = new_lead_province.name

			if products:
				existing_prods = {item.product_type for item in lead.get("preferred_product_type", [])}
				for p in products:
					if p.name not in existing_prods:
						lead.append("preferred_product_type", {"product_type": p.name})

			lead.save(ignore_permissions=True)
			frappe.db.commit()
			break
		except frappe.TimestampMismatchError:
			if attempt < max_retries - 1:
				time.sleep(1)
				continue
			frappe.log_error(f"Lead {lead_name} Update: Max retries reached (Timestamp mismatch)")
		except Exception:
			frappe.log_error(f"Lead {lead_name} Update: Unexpected Error", frappe.get_traceback())
			break

	update_contact_summary_timestamp(conversation_id)
	return True


def update_contact_summary_timestamp(conversation_id):
	"""Updates Contact timestamp without loading full documents"""
	contacts = get_contacts_by_conversation_id(conversation_id)
	if contacts:
		for contact in contacts:
			try:
				frappe.db.set_value(
					"Contact",
					contact.name,
					"last_summarize_time",
					frappe.utils.now_datetime(),
					update_modified=False,
				)
			except Exception:
				frappe.log_error(f"Error updating last_summarize_time for Contact {contact.name}")
		frappe.db.commit()


def create_lead_todo(lead_name: str, allocated_to: str | None):
	"""Create a ToDo assignment for a Lead."""
	if not allocated_to:
		return
	todo_doc = cast(Any, frappe.new_doc("ToDo"))
	todo_doc.description = f"Assignment Rule for Lead {lead_name}"
	todo_doc.priority = "Medium"
	todo_doc.reference_type = "Lead"
	todo_doc.reference_name = lead_name
	todo_doc.allocated_to = allocated_to
	todo_doc.insert()


def transfer_lead_todos(from_lead_name: str, to_lead_name: str):
	"""Transfer all ToDo assignments (open and closed) from one lead to another."""
	loser_todos = frappe.get_all(
		"ToDo", filters={"reference_type": "Lead", "reference_name": from_lead_name}, fields=["name"]
	)
	for todo in loser_todos:
		todo_doc = cast(Any, frappe.get_doc("ToDo", todo.name))
		todo_doc.reference_name = to_lead_name
		if todo_doc.description == f"Assignment Rule for Lead {from_lead_name}":
			todo_doc.description = f"Assignment Rule for Lead {to_lead_name}"
		todo_doc.save(ignore_permissions=True)


def sync_lead_is_assigned():
	frappe.db.sql(
		"""
		UPDATE `tabLead`
		SET is_assigned = 1
		WHERE
			_assign IS NOT NULL
			AND _assign != ''
			AND _assign != '[]'
			AND is_assigned = 0
			AND modified >= NOW() - INTERVAL 30 MINUTE
	"""
	)

	frappe.db.sql(
		"""
		UPDATE `tabLead`
		SET is_assigned = 0
		WHERE (
			_assign IS NULL
			OR _assign = ''
			OR _assign = '[]'
		)
		AND is_assigned = 1
        AND modified >= NOW() - INTERVAL 30 MINUTE
	"""
	)

	frappe.db.commit()


def auto_nurture_leads():
	"""
	Auto-transition Leads to Nurturing status if no customer or sales message for 48 hours.
	Triggered via scheduler cron. Checked against CRM Settings 'auto_nurture_leads'.
	"""
	enabled = get_crm_settings().get("auto_nurture_leads", 0)
	if not enabled:
		return

	cutoff_time = frappe.utils.add_to_date(frappe.utils.now_datetime(), hours=-48)
	leads = frappe.get_all(
		"Lead",
		filters=[
			["status", "=", "Prospecting"],
			["creation", "<", cutoff_time],
		],
		fields=[
			"name",
			"last_customer_message_at",
			"last_sales_message_at",
			"last_message_at",
			"creation",
		],
	)

	target_leads = []
	for lead in leads:
		msg_times = [
			lead.last_customer_message_at,
			lead.last_sales_message_at,
			lead.last_message_at,
		]
		valid_msg_times = []
		for t in msg_times:
			if t:
				dt = get_datetime(t)
				if dt:
					valid_msg_times.append(dt)

		cutoff_dt = get_datetime(cutoff_time)
		if cutoff_dt:
			if valid_msg_times:
				latest_msg = max(valid_msg_times)
				if latest_msg < cutoff_dt:
					target_leads.append(lead.name)
			else:
				creation_dt = get_datetime(lead.creation)
				if creation_dt and creation_dt < cutoff_dt:
					target_leads.append(lead.name)

	if target_leads:
		frappe.db.set_value("Lead", target_leads, "status", "Nurturing")


@frappe.whitelist()
def get_lead_name_by_conversation(conversation_id):
	return get_lead_name_by_conversation_id(conversation_id) if conversation_id else None


@frappe.whitelist()
def get_lead_by_conversation_id(conversation_id):
	response_dict = cast(dict[str, Any], frappe.response)
	if not conversation_id:
		response_dict["leads"] = []
		return

	contacts = frappe.get_all("Contact", filters={"pancake_conversation_id": conversation_id}, pluck="name")
	if not contacts:
		response_dict["leads"] = []
		return

	lead_names = frappe.get_all(
		"Dynamic Link",
		filters={"parent": ["in", contacts], "parenttype": "Contact", "link_doctype": "Lead"},
		pluck="link_name",
	)

	if not lead_names:
		response_dict["leads"] = []
		return

	leads = frappe.get_all(
		"Lead",
		filters={"name": ["in", lead_names]},
		fields=["name", "first_reach_at", "creation", "modified"],
	)

	response_dict["leads"] = leads


@frappe.whitelist()
def fix_duplicate_conversation_leads(enqueue=False):
	sql = """
	WITH conv_leads AS (
		SELECT
			c.pancake_conversation_id,
			l.name AS lead_name,
			l.phone,
			COALESCE(l.first_reach_at, l.creation) AS reach_time,
			CASE WHEN l.phone IS NULL OR l.phone = '' THEN 0 ELSE 1 END AS has_phone
		FROM `tabDynamic Link` dl
		JOIN `tabContact` c ON c.name = dl.parent AND dl.parenttype = 'Contact'
		JOIN `tabLead` l ON l.name = dl.link_name AND dl.link_doctype = 'Lead'
		WHERE c.pancake_conversation_id IS NOT NULL AND c.pancake_conversation_id != ''
	),
	conv_stats AS (
		SELECT pancake_conversation_id,
			   COUNT(*) AS lead_count,
			   COUNT(DISTINCT NULLIF(phone,'')) AS distinct_phones
		FROM conv_leads
		GROUP BY pancake_conversation_id
		HAVING COUNT(*) > 1
	),
	ranked AS (
		SELECT cl.*,
			   ROW_NUMBER() OVER (
				   PARTITION BY cl.pancake_conversation_id
				   ORDER BY cl.reach_time ASC
			   ) AS rn
		FROM conv_leads cl
		JOIN conv_stats cs ON cs.pancake_conversation_id = cl.pancake_conversation_id
		WHERE cs.distinct_phones <= 1
	)
	SELECT
		r1.lead_name AS master_lead,
		r2.lead_name AS duplicate_lead,
		r1.pancake_conversation_id
	FROM ranked r1
	JOIN ranked r2
	  ON r1.pancake_conversation_id = r2.pancake_conversation_id
	 AND r1.rn = 1 AND r2.rn > 1
	ORDER BY r1.pancake_conversation_id;
	"""

	pairs = frappe.db.sql(sql, as_dict=True)

	if str(enqueue).lower() in ["true", "1", "yes"]:
		frappe.enqueue(
			"erpnext.crm.doctype.lead.lead_methods.process_fix_duplicate_conversations",
			pairs=pairs,
			queue="long",
			timeout=3600,
		)
		return f"Enqueued fix for {len(pairs)} duplicate leads."
	else:
		process_fix_duplicate_conversations(pairs)
		return f"Processed {len(pairs)} duplicate leads directly."


def process_fix_duplicate_conversations(pairs):
	processed_count = 0
	for row in pairs:
		master_lead = row.master_lead
		duplicate_lead = row.duplicate_lead

		try:
			# Skip if it was already deleted in a previous iteration
			if not frappe.db.exists("Lead", master_lead) or not frappe.db.exists("Lead", duplicate_lead):
				continue

			master_doc = cast("Lead", frappe.get_doc("Lead", master_lead))
			loser_doc = cast("Lead", frappe.get_doc("Lead", duplicate_lead))

			if master_doc.name == loser_doc.name:
				continue

			# Standard merge pipeline
			_transfer_lead_fields(master_doc, loser_doc)
			_transfer_child_tables(master_doc, loser_doc)
			_merge_tags(master_doc, loser_doc)
			_merge_system_fields(master_doc, loser_doc)
			_merge_assign(master_doc, loser_doc)
			if loser_doc.name and master_doc.name:
				_transfer_notes(loser_doc.name, master_doc)

				_relink_dynamic_links(loser_doc.name, master_doc.name)
				_relink_downstream_docs(loser_doc.name, master_doc.name)
				transfer_lead_todos(loser_doc.name, master_doc.name)

				master_doc.set_first_lead_source()
			master_doc.save(ignore_permissions=True)

			frappe.delete_doc("Lead", loser_doc.name, ignore_permissions=True)

			frappe.db.commit()
			print(f"[{processed_count + 1}/1000] Successfully merged {duplicate_lead} into {master_lead}")

			processed_count += 1
			if processed_count >= 1000:
				print("Reached 1000 successful merges. Stopping as requested.")
				break

		except Exception as e:
			frappe.db.rollback()
			frappe.log_error(
				f"Bulk Conversation Merge: Failed to merge {duplicate_lead} into {master_lead}: {e}",
				"Lead Merge Error",
			)
			print(f"Error merging {duplicate_lead} into {master_lead}: {e}")


@frappe.whitelist()
def reassign_leads_in_bulk(lead_names, assignment_rule=None, enqueue=False):
	if isinstance(lead_names, str):
		lead_names = frappe.parse_json(lead_names)

	if not lead_names:
		return {"status": "failed", "message": "No leads provided."}

	if sbool(enqueue) is True:
		frappe.enqueue(
			"erpnext.crm.doctype.lead.lead_methods.reassign_leads_in_bulk",
			lead_names=lead_names,
			assignment_rule=assignment_rule,
			enqueue=False,
			queue="long",
		)
		return {"status": "success", "message": "Enqueued lead reassignment", "enqueued": True, "count": len(lead_names)}

	frappe.db.set_value(
		"Lead",
		{"name": ("in", lead_names)},
		{"is_assigned": 0, "primary_sale": None, "lead_owner": None, "_assign": None},
	)

	frappe.db.set_value(
		"ToDo",
		{"reference_type": "Lead", "reference_name": ("in", lead_names), "status": "Open"},
		"status",
		"Cancelled",
	)
	frappe.db.commit()

	rule_doc = cast(Any, frappe.get_doc("Assignment Rule", assignment_rule)) if assignment_rule else None
	for name in lead_names:
		try:
			if rule_doc:
				doc = frappe.get_doc("Lead", name)
				rule_doc.apply_assign(doc)
			else:
				apply(doctype="Lead", name=name)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Failed to auto-assign Lead {name}", message=frappe.get_traceback())

	return {"status": "success", "processed": len(lead_names)}
