
import json
from typing import TYPE_CHECKING

from erpnext.crm.doctype.lead_product.lead_product_dao import get_lead_product, create_lead_product
from erpnext.crm.doctype.lead.lead_dao import (
	get_lead_by_name,
	get_lead_name_by_conversation_id
)
from erpnext.crm.doctype.lead_budget.lead_budget_dao import find_range_budget
from erpnext.crm.doctype.lead_demand.lead_demand_dao import get_lead_purpose
from erpnext.config.config import config
from frappe.www.contact import get_contacts_by_conversation_id

import frappe 
from frappe import _
from frappe.utils import validate_phone_number, get_datetime

import time

if TYPE_CHECKING:
	from frappe.model.document import Document

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
		conversation_id = doc.get("pancake_data", {}).get("conversation_id")
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

	pancake_list_tags = doc.get("pancake_tags", [])
	pancake_phone = doc.get("phone", "")
	is_valid_phone = validate_phone_number(pancake_phone)
	if is_valid_phone is False:
		doc["phone"] = ""
	
	pancake_list_tags = [transform_price_label(tag) for tag in pancake_list_tags]
	
	# Check if lead exists by conversation_id
	page_id = doc.get("pancake_data", {}).get("page_id")
	conversation_id = doc.get("pancake_data", {}).get("conversation_id")

	if conversation_id:
		existing_lead_name = get_lead_name_by_conversation_id(conversation_id)
		if existing_lead_name:
			existing_doc = frappe.get_doc("Lead", existing_lead_name)
			existing_doc.link_to_contacts(
				pancake_data=doc.get("pancake_data", {})
			)
			return existing_doc

	# Check if lead exists by phone
	if is_valid_phone and pancake_phone:
		existing_lead_name = frappe.db.get_value("Lead", {"phone": pancake_phone}, "name")
		if existing_lead_name:
			existing_doc = frappe.get_doc("Lead", existing_lead_name)
			if conversation_id and page_id:
				existing_doc.link_to_contacts(
					pancake_data=doc.get("pancake_data", {})
				)
			return existing_doc

	frappe_doc = frappe.get_doc(doc)
	try:
		"""
		Insert a new Lead
		"""
		frappe_doc = frappe_doc.insert()
		if len(pancake_list_tags) > 0:
			for tag in pancake_list_tags:
				frappe_doc.add_tag(tag)

		# only exist when migrate from pancake
		# lead reach at before 2025/06/15 21:00:00
		if frappe_doc.first_reach_at  and  \
			get_datetime(frappe_doc.first_reach_at) < get_datetime(config.DATE_ASSIGN_LEAD_OWNER):
			try:
				todo_doc = frappe.new_doc("ToDo")
				todo_doc.description = f"Assignment Rule for Lead {frappe_doc.name}"
				todo_doc.priority =  "Medium"
				todo_doc.reference_type= "Lead"
				todo_doc.reference_name = frappe_doc.name

				todo_doc.allocated_to = frappe_doc.lead_owner
				todo_doc.insert()
			except Exception as e :
				frappe.log_error(e)
		
		return frappe_doc
	except Exception as e:
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
            if new_name:  # Only add clause if new_name is not empty
                name_case_when_clauses.append(f"""
                    WHEN name = %s THEN
                        CASE
                            WHEN first_name IS NULL OR first_name = '' OR first_name = 'Chưa rõ' THEN %s
                            ELSE first_name
                        END
                """)
                # Parameters for this clause: lead_id (for outer WHEN) and new_name (for inner THEN)
                sql_params_name.extend([lead_id, new_name])

            # Build CASE WHEN clauses for phone with nested conditions
            if new_phone:  # Only add clause if new_phone is not empty
                phone_case_when_clauses.append(f"""
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

    except Exception as e:
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
		doc.pop("flags", None)
		try:
			pancake_phone = doc.get("phone", "")
			is_valid_phone = validate_phone_number(pancake_phone)
			if is_valid_phone is False:
				doc["phone"] = ""

			pancake_list_tags = doc.get("pancake_tags", [])
			pancake_list_tags = [transform_price_label(tag) for tag in pancake_list_tags]
			
			try:
				existing_doc = frappe.get_doc(doc["doctype"], doc["docname"])
			except (frappe.DoesNotExistError, Exception):
				conversation_id = doc.get("pancake_data", {}).get("conversation_id")
				lead_name = get_lead_name_by_conversation_id(conversation_id) if conversation_id else None
				
				if lead_name:
					existing_doc = frappe.get_doc(doc["doctype"], lead_name)
				else:
					raise

			# exist phone not update
			if existing_doc.phone and existing_doc.phone != "":
				doc["phone"] = existing_doc.phone

			# Check if the new phone number already exists in another lead
			new_phone = doc.get("phone")
			if new_phone:
				existing_doc = handle_duplicate_and_merge(existing_doc, new_phone)
			
			if existing_doc.lead_name  and existing_doc.lead_name != "" and existing_doc.lead_name != "Chưa rõ":
				doc["first_name"] = existing_doc.lead_name
				doc["lead_name"] = existing_doc.lead_name

			existing_doc.update(doc)
			existing_doc.save(ignore_permissions=True)
			frappe.db.commit()
			
			contact = None
			try:
				contact = frappe.get_value(
					"Contact",
					{
						"pancake_page_id": doc.get("pancake_data", {}).get("page_id", None),
						"pancake_conversation_id": doc.get("pancake_data", {}).get("conversation_id", None)
					},
				)
			
			except Exception as e:
				contact = None

			if contact: 
				contact_doc = frappe.get_doc("Contact", contact)
				contact_doc.last_message_time =  doc.get("pancake_data", {}).get("latest_message_at")
				contact_doc.save(ignore_permissions=True)

			try: 
				if pancake_list_tags:
					for tag in pancake_list_tags:
						existing_doc.add_tag(tag)
			except Exception as e:
				pass
			
			results.append({
				"conversation_id": doc.get("pancake_data", {}).get("conversation_id"),
				"name": existing_doc.name
			})

		except Exception:
			results.append({
				"conversation_id": doc.get("pancake_data", {}).get("conversation_id"),
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

	# Re-link loser's contacts to master
	loser_contacts = frappe.get_all("Contact", filters=[
		["Dynamic Link", "link_doctype", "=", "Lead"],
		["Dynamic Link", "link_name", "=", loser_doc.name]
	], fields=["name"])

	try:
		for lc in loser_contacts:
			frappe.db.sql("""
				UPDATE `tabDynamic Link`
				SET link_name = %s
				WHERE link_doctype = 'Lead' AND link_name = %s AND parent = %s
			""", (master_doc.name, loser_doc.name, lc.name))
		
		frappe.delete_doc("Lead", loser_doc.name, ignore_permissions=True, force=1)
		
	except Exception as e:
		frappe.log_error(
			f"Failed to merge lead {loser_doc.name} into {master_doc.name}: {str(e)}. All changes rolled back.",
			"Lead Merge Error"
		)
		raise
	
	return master_doc

def transform_price_label(label: str) -> str:
    return label.replace('<', 'dưới ').replace('>', 'trên ').strip()

def get_lead_province(province : str):
	lead_province = None

	try:
		lead_province = frappe.get_doc("Province", {
			"province_name" : province
		})
	except:
		return None
	return lead_province



@frappe.whitelist(methods=["POST"])
def update_lead_from_summary(data):
	if isinstance(data, str):
		data = frappe.parse_json(data)

	conversation_id = data.get("conversation_id", None)
	if conversation_id is None:
		return 
	lead_name = get_lead_name_by_conversation_id(conversation_id)
	
	if lead_name is None:
		return
	
	# lead not found return not update
	lead = get_lead_by_name(lead_name)
	
	if lead is None: 
		contacts = get_contacts_by_conversation_id(conversation_id)
		if contacts is not None:
			for contact in contacts:
				try: 
					contact_doc = frappe.get_doc('Contact', {'name': contact.name})
					contact_doc.last_summarize_time = frappe.utils.now_datetime()
					contact_doc.save()
				except:
					pass

		return

	budget_to = data.get("budget_to", None)
	budget_from =  None if budget_to else data.get("budget_from", None)
	purpose = data.get("purpose", None)
	product_names = data.get("interested_products", [])
	province = data.get("province", None)
	expected_receiving_date = data.get("expected_receiving_date", None)

	new_lead_budget = find_range_budget(budget_from, budget_to)
	new_lead_purpose = get_lead_purpose(purpose)
	new_expected_receiving_date = expected_receiving_date
	new_lead_province = get_lead_province(province)
	products = []
	if product_names is not None:
		for product_name in product_names:
			lead_product = get_lead_product(product_name)
			if lead_product:
				products.append(lead_product)
			else:
				new_lead_product = create_lead_product(product_name)
				if new_lead_product:
					products.append(new_lead_product)
					
	max_retries = 3
	for attempt in range(max_retries):
		try:
			if new_lead_budget:
				lead.budget_lead = new_lead_budget.name

			if new_lead_purpose:
				lead.purpose_lead = new_lead_purpose.name

			if new_expected_receiving_date:
				lead.expected_delivery_date	= new_expected_receiving_date
			
			if new_lead_province:
				lead.province = new_lead_province.name

			for product in products:
				if lead.preferred_product_type is not None:
					existing_products = {item.product_type for item in lead.preferred_product_type}
					if product.name not in existing_products:
						lead.append("preferred_product_type", {
							"product_type": product.name
						})

			lead.save(ignore_permissions=True)
			break
		except Exception as e:
			if e is frappe.TimestampMismatchError:
				frappe.log_error(
					f"Attempt {attempt + 1}/{max_retries}: Timestamp mismatch for Lead {lead_name}. Retrying...",
					frappe.get_traceback(),
				)
			else:
				frappe.log_error(
					"An unexpected error occurred while updating contact summary time.",
					frappe.get_traceback(),
				)
			if attempt < max_retries - 1:
				time.sleep(1)
				lead.reload()
			else:
				break
	#update last summarize at 
	contacts = get_contacts_by_conversation_id(conversation_id)
	if contacts is not None:
		for contact in contacts:
			contact_doc = frappe.get_doc('Contact', {'name': contact.name})
			contact_doc.last_summarize_time = frappe.utils.now_datetime()
			contact_doc.save()

	return True
