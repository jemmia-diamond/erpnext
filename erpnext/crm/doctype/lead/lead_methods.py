import json
from typing import TYPE_CHECKING

import frappe 
from frappe import _
from frappe.utils import validate_phone_number
import re

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
		try:
			inserted_doc = insert_lead(doc)
			if inserted_doc:
				result.append(inserted_doc.name)
			else:
				result.append(None)
		except Exception:
			result.append(None)
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
	
	frappe_doc = frappe.get_doc(doc)
	try:
		"""
		Insert a new Lead
		"""
		frappe_doc = frappe_doc.insert()
		if len(pancake_list_tags) > 0:
			for tag in pancake_list_tags:
				frappe_doc.add_tag(transform_price_label(tag))
		return frappe_doc
	except Exception as e:
		try: 
			check_exist_doc = frappe.get_doc(frappe_doc.doctype, frappe_doc.name)
			if check_exist_doc:
				return check_exist_doc 
			return None 
		except Exception as get_exception:
			pattern = r'CRM-LEAD-\d+-\d+'
			match = re.search(pattern, str(e))
			if match:
				reference_frappe_doc_name = match.group(0)
				return frappe.get_doc(frappe_doc.doctype, reference_frappe_doc_name)
			return None

@frappe.whitelist(methods=["POST", "PUT"])
def update_lead_by_batch(docs):
	"""Bulk update leads

	:param docs: JSON list of documents to be updated remotely. Each document must have `docname` property"""
	docs = json.loads(docs)
	failed_docs = []
	for doc in docs:
		doc.pop("flags", None)
		try:
			pancake_phone = doc.get("phone", "")
			is_valid_phone = validate_phone_number(pancake_phone)
			if is_valid_phone is False:
				doc["phone"] = ""

			existing_doc = frappe.get_doc(doc["doctype"], doc["docname"])
			existing_doc.update(doc)
			existing_doc.save()
			pancake_list_tags = doc.get("pancake_tags", [])
			
			try: 
				if pancake_list_tags:
					for tag in pancake_list_tags:
						existing_doc.add_tag(transform_price_label(tag))
			except Exception as e:
				pass

		except Exception:
			failed_docs.append({"doc": doc, "exc": frappe.utils.get_traceback()})

	return {"failed_docs": failed_docs}

def transform_price_label(label: str) -> str:
    return label.replace('<', 'dưới ').replace('>', 'trên ').strip()
