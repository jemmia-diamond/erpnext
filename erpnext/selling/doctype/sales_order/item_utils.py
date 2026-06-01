SKU_LENGTH_JEWELRY = 21
SKU_PREFIX_TEMPORARY_JEWELRY = "SPT"
SKU_PREFIX_DIAMOND = "AJ"
SKU_PREFIX_DIAMOND_TEMPORARY = "GIA"
SKU_PREFIX_GIFT = "QT"

def is_gift_item(item):
	sku = str(getattr(item, "sku", "") or "")
	return sku.startswith(SKU_PREFIX_GIFT)

def is_gift_item_by_name(item):
	name = str(getattr(item, "item_name", "") or "").lower()
	return "quà tặng" in name

def is_warranty_item(item):
	name = str(getattr(item, "item_name", "") or "").lower()
	return "bảo hành" in name

def is_jewelry_item(item):
	sku = str(getattr(item, "sku", "") or "")
	return sku.startswith(SKU_PREFIX_TEMPORARY_JEWELRY) or len(sku) == SKU_LENGTH_JEWELRY

def is_diamond_item(item):
	sku = str(getattr(item, "sku", "") or "")
	return sku.startswith(SKU_PREFIX_DIAMOND) or sku.startswith(SKU_PREFIX_DIAMOND_TEMPORARY)

def is_diamond_item_code(item_code):
	item_code = str(item_code or "")
	return item_code.startswith(SKU_PREFIX_DIAMOND) or item_code.startswith(SKU_PREFIX_DIAMOND_TEMPORARY)

def get_gia_from_item(item):
	sku = str(getattr(item, "sku", "") or "")
	pos = sku.find("GIA")
	if pos < 0:
		return None
	start = pos + 3
	end = start + 10
	return sku[start:end] if end <= len(sku) else None
