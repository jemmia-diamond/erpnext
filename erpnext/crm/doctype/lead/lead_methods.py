
import json
import re
import time
from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.utils import get_datetime, validate_phone_number
from frappe.www.contact import get_contacts_by_conversation_id

from erpnext.config.config import config
from erpnext.crm.doctype.lead.lead import Lead
from erpnext.crm.doctype.lead.lead_dao import get_lead_by_name, get_lead_name_by_conversation_id
from erpnext.crm.doctype.lead_budget.lead_budget_dao import find_range_budget
from erpnext.crm.doctype.lead_demand.lead_demand_dao import get_lead_purpose
from erpnext.crm.doctype.lead_product.lead_product_dao import create_lead_product, get_lead_product

if TYPE_CHECKING:
	from frappe.model.document import Document

def is_non_empty(value: str | None) -> bool:
	return bool(value and value.strip())

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
	phone = re.sub(r'[\s\-\(\)]', '', phone.strip())
	if phone.startswith('+'):
		phone = phone[1:]
	if phone.startswith('00'):
		phone = phone[2:]
	if phone.startswith('840') and len(phone) >= 12:
		phone = '84' + phone[3:]
	elif phone.startswith('0'):
		phone = '84' + phone[1:]

	return phone

@frappe.whitelist(methods=["POST", "PUT"])
def insert_lead_by_batch(docs=None):
	"""Insert multiple lead

	:param docs: JSON or list of dict objects to be inserted in one request"""
	if isinstance(docs, str):
		docs = json.loads(docs)

	if len(docs) > 200:
		frappe.throw(_("Only 200 inserts allowed in one request"))

	result = []
	for doc in docs:
		doc = doc.copy()
		pancake_data = doc.get("pancake_data", {})
		conversation_id = pancake_data.get("conversation_id")

		if not is_non_empty(conversation_id):
			frappe.logger().warning(
				"insert_lead_by_batch: missing conversation_id",
				exc_info=False
			)
			result.append({
				"name": None,
				"conversation_id": conversation_id
			})
			continue

		try:
			inserted_doc = insert_lead(doc)
			if inserted_doc:
				result.append({
					"name": inserted_doc.name,
					"conversation_id": conversation_id
				})
			else:
				result.append({
					"name": None,
					"conversation_id": conversation_id
				})
		except Exception:
			result.append({
				"name": None,
				"conversation_id": conversation_id
			})
	return result

def insert_lead(doc) -> "Document":
	"""Inserts document and returns parent document object with appended child document
	if `doc` is child document else returns the inserted document object

	:param doc: doc to insert (dict)"""

	doc = frappe._dict(doc)
	if frappe.is_table(doc.doctype):
		if not (doc.parenttype and doc.parent and doc.parentfield):
			frappe.throw(_("Parenttype, Parent and Parentfield are required to insert a child record"))

		# inserting a child record
		parent = frappe.get_doc(doc.parenttype, doc.parent)
		parent.append(doc.parentfield, doc)
		parent.save()
		return parent

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
			existing_doc: Lead = frappe.get_doc("Lead", existing_lead_name)
			existing_doc.link_to_contacts(
				pancake_data=pancake_data
			)
			return existing_doc

	# Check if lead exists by phone
	if is_valid_phone and is_non_empty(pancake_phone):
		existing_lead_name = frappe.db.get_value("Lead", {"phone": pancake_phone}, "name")
		if existing_lead_name:
			existing_doc = frappe.get_doc("Lead", existing_lead_name)
			if conversation_id and page_id:
				existing_doc.link_to_contacts(
					pancake_data=pancake_data
				)
			return existing_doc

	frappe_doc = frappe.get_doc(doc)
	try:
		"""
		Insert a new Lead
		"""
		frappe_doc = frappe_doc.insert()

		if pancake_list_tags:
			for tag in pancake_list_tags:
				frappe_doc.add_tag(tag)

		# only exist when migrate from pancake
		# lead reach at before 2025/06/15 21:00:00
		if frappe_doc.first_reach_at  and  \
			get_datetime(frappe_doc.first_reach_at) < get_datetime(config.DATE_ASSIGN_LEAD_OWNER):
			try:
				create_lead_todo(frappe_doc.name, frappe_doc.lead_owner)
			except Exception as e:
				frappe.log_error(e)

		return frappe_doc
	except Exception:
		try:
			existing_doc = frappe.get_doc(frappe_doc.doctype, frappe_doc.name)
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
            new_name = doc.get("new_name")
            new_phone = doc.get("new_phone")

            if not lead_id:
                failed_docs.append({"doc": doc, "exc": "Missing 'docname' (lead ID). Skipping this document."})
                continue # Skip this document if docname is missing

            ids_to_update.append(lead_id)

            # Build CASE WHEN clauses for first_name with nested conditions
            if is_non_empty(new_name):  # Only add clause if new_name is not empty
                name_case_when_clauses.append("""
                    WHEN name = %s THEN
                        CASE
                            WHEN first_name IS NULL OR first_name = '' OR first_name = 'Chưa rõ' THEN %s
                            ELSE first_name
                        END
                """)
                # Parameters for this clause: lead_id (for outer WHEN) and new_name (for inner THEN)
                sql_params_name.extend([lead_id, new_name])

            # Build CASE WHEN clauses for phone with nested conditions
            if is_non_empty(new_phone):  # Only add clause if new_phone is not empty
                phone_case_when_clauses.append("""
                    WHEN name = %s THEN
                        CASE
                            WHEN phone IS NULL OR phone = '' THEN %s
                            ELSE phone
                        END
                """)
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
	if isinstance(docs, str):
		docs = json.loads(docs)
	failed_docs = []
	results = []
	for doc in docs:
		doc = doc.copy()
		doc.pop("flags", None)
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

			existing_doc = None
			try:
				existing_doc = frappe.get_doc(doc["doctype"], doc["docname"])
			except (frappe.DoesNotExistError, Exception):
				conversation_id = pancake_data.get("conversation_id")
				lead_name = get_lead_name_by_conversation_id(conversation_id) if is_non_empty(conversation_id) else None

				if lead_name:
					existing_doc = frappe.get_doc(doc["doctype"], lead_name)
				else:
					doc.pop("docname", None)
					existing_doc = insert_lead(doc)

			# exist phone not update
			if existing_doc.phone and existing_doc.phone != "":
				doc["phone"] = existing_doc.phone

			# Check if the new phone number already exists in another lead
			new_phone = doc.get("phone")
			if is_non_empty(new_phone):
				existing_doc = handle_duplicate_and_merge(
					existing_doc,
					new_phone
				)

			if existing_doc.lead_name  and existing_doc.lead_name != "" and existing_doc.lead_name != "Chưa rõ":
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

			results.append({
				"conversation_id": pancake_data.get("conversation_id"),
				"name": existing_doc.name
			})

		except Exception:
			results.append({
				"conversation_id": pancake_data.get("conversation_id"),
				"name": None
			})
			failed_docs.append({"doc": doc, "exc": frappe.utils.get_traceback()})

	return {"results": results, "failed_docs": failed_docs}


def handle_duplicate_and_merge(existing_doc, new_phone):
	"""
	Check if new_phone belongs to another lead.
	If so, keep the oldest lead (by first_reach_at), merge contacts, and delete the duplicate.
	Returns the 'master' document that survived.
	"""
	if not is_non_empty(new_phone):
		return existing_doc

	new_phone = normalize_phone_number(new_phone)
	conflicting_lead = frappe.db.get_value("Lead", {"phone": new_phone}, "name")

	if not conflicting_lead or conflicting_lead == existing_doc.name:
		return existing_doc

	conflicting_doc = frappe.get_doc("Lead", conflicting_lead)

	# Determine which lead is older (Master) and which is newer (Loser)
	is_existing_older = False
	if existing_doc.first_reach_at and conflicting_doc.first_reach_at:
		if get_datetime(existing_doc.first_reach_at) < get_datetime(conflicting_doc.first_reach_at):
			is_existing_older = True
	elif existing_doc.first_reach_at: # conflicting has no date
		is_existing_older = True

	if is_existing_older:
		master_doc = existing_doc
		loser_doc = conflicting_doc
	else:
		master_doc = conflicting_doc
		loser_doc = existing_doc

	try:
		frappe.db.savepoint("lead_merge")
		# Re-link loser's contacts and addresses to master
		_relink_dynamic_links(loser_doc.name, master_doc.name)

		# Re-link downstream docs to master
		_relink_downstream_docs(loser_doc.name, master_doc.name)

		if not master_doc.region and loser_doc.region:
			master_doc.region = loser_doc.region

		if not master_doc.province and loser_doc.province:
			master_doc.province = loser_doc.province

		if not master_doc.budget_lead and loser_doc.budget_lead:
			master_doc.budget_lead = loser_doc.budget_lead

		if not master_doc.lead_owner and loser_doc.lead_owner:
			master_doc.lead_owner = loser_doc.lead_owner

		transfer_lead_todos(loser_doc.name, master_doc.name)

		frappe.delete_doc("Lead", loser_doc.name, ignore_permissions=True, force=1)

		master_doc.set_first_lead_source()

	except Exception as e:
		frappe.db.rollback(save_point="lead_merge")
		frappe.log_error(
			f"Failed to merge lead {loser_doc.name} into {master_doc.name}: {e!s}. All changes rolled back.",
			"Lead Merge Error"
		)
		raise

	return master_doc


def _relink_dynamic_links(from_lead: str, to_lead: str):
	"""Re-link Contact and Address Dynamic Link records from one lead to another."""
	for doctype in ("Contact", "Address"):
		linked_docs = frappe.get_all(doctype, filters=[
			["Dynamic Link", "link_doctype", "=", "Lead"],
			["Dynamic Link", "link_name", "=", from_lead]
		], fields=["name"])

		for doc in linked_docs:
			frappe.db.sql("""
				UPDATE `tabDynamic Link`
				SET link_name = %s
				WHERE link_doctype = 'Lead' AND link_name = %s AND parent = %s
			""", (to_lead, from_lead, doc.name))

def _relink_downstream_docs(from_lead: str, to_lead: str):
	"""Re-link all downstream documents, logs, and audits from one lead to another."""
	# Issues linked via lead field
	frappe.db.sql("""
		UPDATE `tabIssue`
		SET `lead` = %s
		WHERE `lead` = %s
	""", (to_lead, from_lead))

	# Prospect Lead links
	frappe.db.sql("""
		UPDATE `tabProspect Lead`
		SET lead = %s, lead_name = (SELECT lead_name FROM `tabLead` WHERE name = %s)
		WHERE lead = %s
	""", (to_lead, to_lead, from_lead))

	# Customers linked via lead_name
	frappe.db.sql("""
		UPDATE `tabCustomer`
		SET lead_name = %s
		WHERE lead_name = %s
	""", (to_lead, from_lead))

	# Appointments linked via lead
	frappe.db.sql("""
		UPDATE `tabAppointment`
		SET `lead` = %s
		WHERE `lead` = %s
	""", (to_lead, from_lead))

	# Communications referencing this lead
	frappe.db.sql("""
		UPDATE `tabCommunication`
		SET reference_name = %s
		WHERE reference_doctype = 'Lead' AND reference_name = %s
	""", (to_lead, from_lead))

	# File attachments
	frappe.db.sql("""
		UPDATE `tabFile`
		SET attached_to_name = %s
		WHERE attached_to_doctype = 'Lead' AND attached_to_name = %s
	""", (to_lead, from_lead))

	# Email Queue
	frappe.db.sql("""
		UPDATE `tabEmail Queue`
		SET reference_name = %s
		WHERE reference_doctype = 'Lead' AND reference_name = %s
	""", (to_lead, from_lead))

	# Version Audit Trail
	frappe.db.sql("""
		UPDATE `tabVersion`
		SET docname = %s
		WHERE ref_doctype = 'Lead' AND docname = %s
	""", (to_lead, from_lead))

	# Comments timeline
	frappe.db.sql("""
		UPDATE `tabComment`
		SET reference_name = %s
		WHERE reference_doctype = 'Lead' AND reference_name = %s
	""", (to_lead, from_lead))

def transform_price_label(label: str) -> str:
    return label.replace('<', 'dưới ').replace('>', 'trên ').strip()

def get_lead_province(province : str):
	lead_province = None

	try:
		lead_province = frappe.get_doc("Province", {
			"province_name" : province
		})
	except Exception:
		return None
	return lead_province

@frappe.whitelist(methods=["POST"])
def update_lead_from_summary(data):
	if isinstance(data, str):
		data = frappe.parse_json(data)

	conversation_id = data.get("conversation_id")
	if not is_non_empty(conversation_id):
		frappe.logger().warning(
			"update_lead_from_summary: missing conversation_id",
			exc_info=False
		)
		return

	lead_name = get_lead_name_by_conversation_id(conversation_id)
	if not lead_name:
		update_contact_summary_timestamp(conversation_id)
		return

	lead = get_lead_by_name(lead_name)
	if not lead:
		update_contact_summary_timestamp(conversation_id)
		return

	budget_to = data.get("budget_to")
	budget_from = None if budget_to else data.get("budget_from")
	purpose = data.get("purpose")
	product_names = data.get("interested_products", [])
	province = data.get("province")
	expected_receiving_date = data.get("expected_receiving_date")

	new_lead_budget = find_range_budget(budget_from, budget_to)
	new_lead_purpose = get_lead_purpose(purpose)
	new_lead_province = get_lead_province(province)

	products = []
	if product_names:
		for product_name in product_names:
			lead_product = get_lead_product(product_name)
			if not lead_product:
				lead_product = create_lead_product(product_name)
			if lead_product:
				products.append(lead_product)
	max_retries = 3
	for attempt in range(max_retries):
		try:
			if attempt > 0:
				lead.reload()

			if new_lead_budget:
				lead.budget_lead = new_lead_budget.name
			if new_lead_purpose:
				lead.purpose_lead = new_lead_purpose.name
			if expected_receiving_date:
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

def create_lead_todo(lead_name: str, allocated_to: str):
	"""Create a ToDo assignment for a Lead."""
	if not allocated_to:
		return
	todo_doc = frappe.new_doc("ToDo")
	todo_doc.description = f"Assignment Rule for Lead {lead_name}"
	todo_doc.priority = "Medium"
	todo_doc.reference_type = "Lead"
	todo_doc.reference_name = lead_name
	todo_doc.allocated_to = allocated_to
	todo_doc.insert()

def transfer_lead_todos(from_lead_name: str, to_lead_name: str):
	"""Transfer open ToDo assignments from one lead to another if the target has none."""
	master_todos = frappe.get_all("ToDo", filters={
		"reference_type": "Lead",
		"reference_name": to_lead_name,
		"status": "Open"
	}, fields=["name"])

	if master_todos:
		return

	loser_todos = frappe.get_all("ToDo", filters={
		"reference_type": "Lead",
		"reference_name": from_lead_name,
		"status": "Open"
	}, fields=["name"])
	for todo in loser_todos:
		todo_doc = frappe.get_doc("ToDo", todo.name)
		todo_doc.reference_name = to_lead_name
		todo_doc.description = f"Assignment Rule for Lead {to_lead_name}"
		todo_doc.save(ignore_permissions=True)

def sync_lead_is_assigned():
	frappe.db.sql("""
		UPDATE `tabLead`
		SET is_assigned = 1
		WHERE
			_assign IS NOT NULL
			AND _assign != ''
			AND _assign != '[]'
			AND is_assigned = 0
			AND modified >= NOW() - INTERVAL 30 MINUTE
	""")

	frappe.db.sql("""
		UPDATE `tabLead`
		SET is_assigned = 0
		WHERE (
			_assign IS NULL
			OR _assign = ''
			OR _assign = '[]'
		)
		AND is_assigned = 1
        AND modified >= NOW() - INTERVAL 30 MINUTE
	""")

	frappe.db.commit()
