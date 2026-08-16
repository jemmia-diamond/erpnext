# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""
Cloudflare R2 Storage Integration for ERPNext
Based on best practices from:
- https://github.com/zerodha/frappe-attachments-s3
- https://github.com/frappe/storage_integration

Upload files directly to Cloudflare R2 (S3-compatible storage)
"""

import datetime
import os
import random
import re
import string
import unicodedata
from urllib.parse import quote, unquote

import boto3
import frappe
import requests
from botocore.client import Config
from botocore.exceptions import ClientError
from frappe import _
from frappe.utils import get_site_path


class R2FileManager:
	"""Manager class for R2 operations"""

	def __init__(self):
		"""Initialize R2 settings from site config"""
		self.settings = self._get_settings()

		if not self.settings.get("enabled"):
			return

		# Initialize S3 client for R2
		self.client = boto3.client(
			"s3",
			endpoint_url=self.settings["endpoint_url"],
			aws_access_key_id=self.settings["access_key_id"],
			aws_secret_access_key=self.settings["secret_access_key"],
			region_name="auto",  # R2 uses 'auto' region
			config=Config(signature_version="s3v4"),
		)
		self.bucket = self.settings["bucket"]
		self.folder_name = self.settings.get("folder_name", "")

	def _get_settings(self):
		"""Get R2 configuration from site config"""
		return {
			"enabled": frappe.conf.get("r2_enabled", False),
			"endpoint_url": frappe.conf.get("r2_endpoint_url"),
			"access_key_id": frappe.conf.get("r2_access_key_id"),
			"secret_access_key": frappe.conf.get("r2_secret_access_key"),
			"bucket": frappe.conf.get("r2_bucket"),
			"folder_name": frappe.conf.get("r2_folder_name", ""),
			"public_url": frappe.conf.get("r2_public_url", ""),
			"signed_url_expiry": frappe.conf.get("r2_signed_url_expiry", 3600),
			"delete_local_after_upload": frappe.conf.get("r2_delete_local_after_upload", True),
		}

	def generate_key(self, file_name, parent_doctype=None, content_hash=None):
		"""
		Generate S3 key with organized folder structure
		"""
		# Clean file name: unquote existing URL encoding, replace spaces/commas with underscores
		file_name = unquote(file_name or "").replace(" ", "_").replace(",", "_")
		# Normalize to NFC so composed characters are consistent
		file_name = unicodedata.normalize("NFC", file_name)
		# Keep Unicode; remove unsafe path/URL characters
		file_name = re.sub(r'[<>:"/\\|?*\[\]{}%#,]', "", file_name)

		# Use content_hash if available (from Frappe), else generate random
		if content_hash:
			# Use last 8 chars of MD5 hash (already computed by Frappe)
			hash_suffix = content_hash[-8:].upper()
		else:
			# Fallback: generate random 8-char key
			hash_suffix = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))

		# Add hash as suffix (before extension)
		# Example: "invoice.pdf" + "A1B2C3D4" → "invoice_A1B2C3D4.pdf"
		name_parts = file_name.rsplit(".", 1)
		if len(name_parts) == 2:
			unique_file_name = f"{name_parts[0]}_{hash_suffix}.{name_parts[1]}"
		else:
			unique_file_name = f"{file_name}_{hash_suffix}"

		# Date-based path
		today = datetime.datetime.now()
		year = today.strftime("%Y")
		month = today.strftime("%m")
		day = today.strftime("%d")

		# Build key path
		site_name = frappe.local.site
		parts = []

		if self.folder_name:
			parts.append(self.folder_name)

		parts.extend([site_name, year, month, day])

		if parent_doctype:
			parts.append(parent_doctype)

		parts.append(unique_file_name)

		return "/".join(parts)

	def upload_file(self, file_path, file_doc):
		"""Upload file to R2 and return S3 key"""
		try:
			parent_doctype = file_doc.attached_to_doctype or "File"
			# Pass content_hash to generate_key for unique suffix
			content_hash = getattr(file_doc, "content_hash", None)
			s3_key = self.generate_key(file_doc.file_name, parent_doctype, content_hash)

			# Determine content type
			content_type = file_doc.get("content_type") or "application/octet-stream"

			# Upload with appropriate args
			extra_args = {
				"ContentType": content_type,
				"Metadata": {
					"site": frappe.local.site,
					# Metadata headers must be ASCII-only; strip accents
					"original_name": unicodedata.normalize("NFKD", str(file_doc.file_name or ""))
					.encode("ascii", "ignore")
					.decode(),
					"is_private": str(file_doc.is_private),
				},
			}
			# Do NOT set ACL headers; R2 may reject ACLs

			self.client.upload_file(file_path, self.bucket, s3_key, ExtraArgs=extra_args)

			frappe.logger().info(f"Uploaded file to R2: {s3_key}")
			return s3_key

		except Exception as e:
			frappe.logger().error(f"R2 Upload Error: {e!s}")
			frappe.throw(_("File Upload Failed. Please try again."))

	def get_file_url(self, s3_key, file_name, is_private):
		"""Generate appropriate URL for file"""
		# Both public and private files use API endpoint
		method = "erpnext.r2_storage.stream_from_r2"
		encoded_key = quote(s3_key, safe="/")
		encoded_name = quote(file_name or "")
		return f"/api/method/{method}?key={encoded_key}&file_name={encoded_name}"

	def read_file(self, s3_key):
		"""Read file from R2"""
		try:
			response = self.client.get_object(Bucket=self.bucket, Key=s3_key)
			return response["Body"].read()
		except Exception as e:
			frappe.logger().error(f"R2 Read Error: {e!s}")
			return None

	def generate_presigned_url(self, s3_key, file_name=None):
		"""Generate presigned URL for private file access"""
		try:
			params = {"Bucket": self.bucket, "Key": s3_key}

			if file_name:
				params["ResponseContentDisposition"] = f"filename={file_name}"

			url = self.client.generate_presigned_url(
				"get_object",
				Params=params,
				ExpiresIn=self.settings["signed_url_expiry"],
			)
			return url
		except Exception as e:
			frappe.logger().error(f"R2 Presigned URL Error: {e!s}")
			return None

	def get_r2_url(self, s3_key, file_name=None, is_private=True):
		"""Get direct R2 URL (public or presigned)"""
		public_url = self.settings.get("public_url")
		if public_url and not is_private:
			encoded_key = quote(s3_key, safe="/")
			return f"{public_url.rstrip('/')}/{encoded_key}"
		return self.generate_presigned_url(s3_key, file_name)

	def delete_file(self, s3_key):
		"""Delete file from R2"""
		try:
			self.client.delete_object(Bucket=self.bucket, Key=s3_key)
			frappe.logger().info(f"Deleted file from R2: {s3_key}")
		except Exception as e:
			frappe.logger().error(f"R2 Delete Error: {e!s}")


def get_r2_manager():
	"""Get cached R2FileManager for current request"""
	if not hasattr(frappe.local, "r2_file_manager"):
		frappe.local.r2_file_manager = R2FileManager()
	return frappe.local.r2_file_manager


# ==============================================================================
# HOOKS - Called automatically by Frappe
# ==============================================================================


def upload_to_r2(doc, method=None):
	"""
	Hook: Called after File document is inserted
	Uploads file to R2 and updates file_url
	"""
	manager = get_r2_manager()
	if not manager.settings.get("enabled"):
		return

	# Skip if already uploaded (file_url contains R2 pattern)
	if doc.file_url and is_r2_file(doc.file_url):
		return

	# Skip if no file_url (remote URL files)
	if not doc.file_url:
		return

	# Skip for certain doctypes
	ignore_doctypes = frappe.conf.get("r2_ignore_doctypes", [])
	if doc.attached_to_doctype in ignore_doctypes:
		return

	try:
		# Get file path on disk
		site_path = get_site_path()
		if not doc.is_private:
			file_path = os.path.join(site_path, "public", "files", doc.file_url.replace("/files/", ""))
		else:
			file_path = os.path.join(
				site_path, "private", "files", doc.file_url.replace("/private/files/", "")
			)

		# Check if file exists
		if not os.path.exists(file_path):
			frappe.logger().warning(f"File not found for upload: {file_path}")
			return

		# Upload to R2
		s3_key = manager.upload_file(file_path, doc)

		# Generate new file URL
		new_file_url = manager.get_file_url(s3_key, doc.file_name, doc.is_private)

		# Update File document
		frappe.db.sql(
			"""UPDATE `tabFile`
			   SET file_url=%s, folder=%s, content_hash=%s
			   WHERE name=%s""",
			(new_file_url, "Home/Attachments", s3_key, doc.name),
		)

		doc.file_url = new_file_url

		# Delete local file if configured
		if manager.settings.get("delete_local_after_upload"):
			try:
				os.remove(file_path)
				frappe.logger().info(f"Deleted local file: {file_path}")
			except Exception as e:
				frappe.logger().warning(f"Could not delete local file: {e}")

		frappe.db.commit()

	except Exception as e:
		frappe.logger().error(f"Error in upload_to_r2: {e!s}")
		frappe.log_error(title="R2 Upload Error")


def delete_from_r2(doc, method=None):
	"""
	Hook: Called when File document is deleted
	Deletes file from R2
	"""
	manager = get_r2_manager()
	if not manager.settings.get("enabled"):
		return

	# Get S3 key from content_hash field
	s3_key = doc.content_hash

	if s3_key and not is_r2_file(doc.file_url):
		# Old file, extract key from file_url
		s3_key = extract_key_from_url(doc.file_url)

	if s3_key:
		manager.delete_file(s3_key)


# ==============================================================================
# API METHODS - Public endpoints
# ==============================================================================


@frappe.whitelist()
def stream_from_r2(key=None, file_name=None):
	"""
	API endpoint to stream private files from R2
	Usage: /api/method/erpnext.r2_storage.stream_from_r2?key=xxx&file_name=yyy
	"""
	if not key:
		frappe.throw(_("Key not provided"))

	manager = get_r2_manager()
	if not manager.settings.get("enabled"):
		frappe.throw(_("R2 not configured"))

	# Decode previously URL-encoded params to avoid double-encoding in presign
	try:
		decoded_key = unquote(key)
		decoded_name = unquote(file_name) if file_name else None
	except Exception:
		decoded_key = key
		decoded_name = file_name

	# Generate presigned URL and redirect
	signed_url = manager.generate_presigned_url(decoded_key, decoded_name)

	if signed_url:
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = signed_url
	else:
		frappe.throw(_("Could not generate download URL"))


@frappe.whitelist()
def migrate_existing_files():
	"""
	Migrate all existing files from local storage to R2
	Can be called from UI or console
	"""
	manager = get_r2_manager()
	if not manager.settings.get("enabled"):
		frappe.throw(_("R2 not configured"))

	# Get all files that are not yet on R2
	files = frappe.get_all(
		"File",
		fields=["name", "file_url", "file_name", "is_private"],
		filters={"file_url": ["!=", ""]},
	)

	migrated = 0
	errors = 0

	for file_data in files:
		# Skip if already on R2
		if is_r2_file(file_data.file_url):
			continue

		try:
			doc = frappe.get_doc("File", file_data.name)
			upload_to_r2(doc, None)
			migrated += 1
		except Exception as e:
			frappe.logger().error(f"Migration error for {file_data.name}: {e!s}")
			errors += 1

	return {
		"migrated": migrated,
		"errors": errors,
		"total": len(files),
	}


@frappe.whitelist()
def get_r2_url(file_url=None, key=None, file_name=None):
	"""
	API endpoint / helper to get direct R2 URL for a file URL or key
	Usage: /api/method/erpnext.r2_storage.get_r2_url?file_url=xxx or ?key=yyy
	"""
	if not file_url and not key:
		frappe.throw(_("file_url or key is required"))

	manager = get_r2_manager()
	if not manager.settings.get("enabled"):
		return file_url

	if file_url and not key:
		key = extract_key_from_url(file_url)

	if not key:
		return file_url

	return manager.get_r2_url(key, file_name)


@frappe.whitelist()
def get_files(
	filters=None, fields=None, or_filters=None, order_by=None, limit_start=0, limit_page_length=None
):
	"""Get File list with r2_file_url computed for every item"""
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	if isinstance(fields, str):
		fields = frappe.parse_json(fields)
	if isinstance(or_filters, str):
		or_filters = frappe.parse_json(or_filters)

	files = frappe.get_list(
		"File",
		filters=filters,
		fields=fields,
		or_filters=or_filters,
		order_by=order_by,
		limit_start=limit_start,
		limit_page_length=limit_page_length,
	)

	return process_file_list(files)


def process_file_list(files):
	"""Attach r2_file_url to a list of File records"""
	if not isinstance(files, list):
		return files

	manager = get_r2_manager()
	is_enabled = manager.settings.get("enabled")

	for f in files:
		if isinstance(f, dict):
			file_url = f.get("file_url")
			key = extract_key_from_url(file_url) if is_enabled else None
			f["r2_file_url"] = (
				manager.get_r2_url(key, f.get("file_name"), f.get("is_private", 1)) if key else file_url
			)

	return files


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================


def is_r2_file(file_url):
	"""Check if file URL indicates file is on R2"""
	if not file_url:
		return False
	return bool(
		re.search(r"(r2\.cloudflarestorage\.com|/api/method/erpnext\.r2_storage\.stream_from_r2)", file_url)
	)


def extract_key_from_url(file_url):
	"""Extract S3 key from file URL"""
	if not file_url:
		return None
	if "/api/method/" in file_url:
		# Extract from API URL
		match = re.search(r"key=([^&]+)", file_url)
		if match:
			return unquote(match.group(1))
	return None


def get_r2_url_for_file(doc_or_name):
	"""Get direct R2 URL for a File doc or name"""
	if isinstance(doc_or_name, str):
		doc = frappe.get_doc("File", doc_or_name)
	else:
		doc = doc_or_name

	if not doc or not doc.file_url:
		return None

	s3_key = doc.content_hash
	if not s3_key or not is_r2_file(doc.file_url):
		s3_key = extract_key_from_url(doc.file_url)

	if not s3_key:
		return doc.file_url

	manager = get_r2_manager()
	return manager.get_r2_url(s3_key, doc.file_name, doc.is_private)


def compress_and_upload_to_r2(download_url, headers, file_name, attached_to_doctype, attached_to_name):
	"""
	Downloads a file, compresses it via Compressor, uploads directly to R2,
	and creates the corresponding Frappe File record.
	Returns the final R2 URL if successful, or None if the compressor is not configured/enabled.
	"""
	manager = get_r2_manager()

	# Get compressor URL
	compressor_url = frappe.conf.get("compressor_service_url")
	if not compressor_url:
		try:
			from erpnext.config.config import config

			compressor_url = getattr(config, "COMPRESSOR_SERVICE_URL", "")
		except ImportError:
			pass

	if not (compressor_url and manager.settings.get("enabled") and hasattr(manager, "client")):
		return None

	object_key = manager.generate_key(file_name, attached_to_doctype)

	presigned_put_url = manager.client.generate_presigned_url(
		"put_object",
		Params={"Bucket": manager.bucket, "Key": object_key, "ContentType": "audio/mpeg"},
		ExpiresIn=3600,
	)

	payload = {"input_url": download_url, "download_headers": headers, "output_upload_url": presigned_put_url}

	compress_url = f"{compressor_url.rstrip('/')}/compress"
	response = requests.post(compress_url, json=payload, timeout=300)
	response.raise_for_status()

	final_r2_url = manager.get_file_url(object_key, file_name, is_private=True)

	# Manually create the File DocType record so it shows up in the UI attachments
	if not frappe.db.exists(
		"File",
		{
			"attached_to_doctype": attached_to_doctype,
			"attached_to_name": attached_to_name,
			"file_url": final_r2_url,
		},
	):
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": file_name,
				"file_url": final_r2_url,
				"attached_to_doctype": attached_to_doctype,
				"attached_to_name": attached_to_name,
				"is_private": 1,
			}
		)
		file_doc.flags.ignore_permissions = True
		file_doc.flags.ignore_file_validate = True
		file_doc.insert()

	return final_r2_url
