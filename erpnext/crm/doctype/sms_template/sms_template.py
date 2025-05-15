# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from erpnext.config.config import config
from erpnext.packages.gapone_client import GapOneClient
from frappe.model.document import Document


class SMSTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		branch_name: DF.Literal[None]
		content: DF.Text | None
		template_name: DF.SmallText | None
		template_staus: DF.Literal["Drafting", "Done"]
		template_type: DF.Literal["Advertisement", "Customer Care"]
	# end: auto-generated types
	pass


@frappe.whitelist()
def get_branches():
	"""
	get branches
	"""
	gap_one_client = GapOneClient(api_key=config.GAPONE_API_KEY)
	branches = gap_one_client.branch.get_branches()
	
	branch_names  = list(map(lambda x: x["name"], branches))
	return branch_names
