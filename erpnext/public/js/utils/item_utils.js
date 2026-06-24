frappe.provide("erpnext.utils.item");

$.extend(erpnext.utils.item, {
	SKU_LENGTH: {
		JEWELRY: 21
	},

	SKU_PREFIX: {
		TEMPORARY_JEWELRY: "SPT",
		DIAMOND: "AJ",
		DIAMOND_TEMPORARY: "GIA",
		GIFT: "QT"
	},

	HRV_PRODUCT_TYPE: {
		PLAIN_CHAIN: "Dây Chuyền Trơn"
	},

	isGiftItem: function(item) {
		return item.sku?.startsWith(erpnext.utils.item.SKU_PREFIX.GIFT);
	},

	isGiftItemByName: function(item) {
		const name_lower = (item.item_name || "").toLowerCase();
		return name_lower.includes("quà tặng");
	},

	isWarrantyItem: function(item) {
		const name_lower = (item.item_name || "").toLowerCase();
		return name_lower.includes("bảo hành");
	},

	isJewelryItem: function(item) {
		return item.sku?.startsWith(erpnext.utils.item.SKU_PREFIX.TEMPORARY_JEWELRY) || 
			   item.sku?.length === erpnext.utils.item.SKU_LENGTH.JEWELRY;
	},

	isDiamondItem: function(item) {
		return item.sku?.startsWith(erpnext.utils.item.SKU_PREFIX.DIAMOND) || 
			   item.sku?.startsWith(erpnext.utils.item.SKU_PREFIX.DIAMOND_TEMPORARY);
	}
});
