import { parsePhoneNumber, isValidPhoneNumber, getCountryCallingCode } from 'libphonenumber-js';

frappe.provide("erpnext.utils");

erpnext.utils.normalize_to_standard_format = function(phone, default_country = "VN") {
    if (!phone) return "";

    try {
        const phoneNumber = parsePhoneNumber(phone, default_country);
        if (phoneNumber && phoneNumber.isValid()) {
            let formatted = phoneNumber.format('E.164');
            return formatted.replace("+", "");
        }
    } catch (error) {
        // parsing failed
    }

    let digits = phone.replace(/\D/g, "");
    if (!digits) return "";

    let country_code = "84";
    try {
        country_code = getCountryCallingCode(default_country);
    } catch (e) {}

    if (digits.startsWith("0") && digits.length >= 9) {
        return country_code + digits.substring(1);
    }

    if (digits.startsWith(country_code + "0") && digits.length >= country_code.length + 9) {
        return country_code + digits.substring(country_code.length + 1);
    }

    return digits;
};

erpnext.utils.is_valid_phone_number = function(phone, default_country = "VN") {
    if (!phone || !String(phone).trim()) return false;
    let phone_str = String(phone).trim();
    
    try {
        if (isValidPhoneNumber(phone_str, default_country)) {
            return true;
        }
    } catch (e) {}

    if (!phone_str.startsWith("+")) {
        try {
            if (isValidPhoneNumber("+" + phone_str, default_country)) {
                return true;
            }
        } catch (e) {}
    }

    return false;
};

erpnext.utils.get_phone_variants = function(phone, default_country = "VN") {
    if (!phone) return [];

    let variants = new Set([phone]);
    let digits = phone.replace(/\D/g, "");
    if (digits) {
        variants.add(digits);
    }

    try {
        const phoneNumber = parsePhoneNumber(phone, default_country);
        if (phoneNumber && phoneNumber.isValid()) {
            let formatted = phoneNumber.format('E.164');
            variants.add(formatted.replace("+", ""));
            
            let national_format = phoneNumber.format('NATIONAL');
            let national_digits = national_format.replace(/\D/g, "");
            if (national_digits) {
                variants.add(national_digits);
            }
        }
    } catch (error) {
        // ignore
    }

    return Array.from(variants);
};

erpnext.utils.check_duplicate_phone = function(mobile_no, doctype="Customer") {
    let variants = erpnext.utils.get_phone_variants(mobile_no);

    let or_filters = [];
    
    // Ensure meta is loaded, though for standard doctypes it usually is. 
    // We will just do a safe check. If meta is not loaded, we assume it has both to be safe, 
    // or we can just push only the fields that exist.
    let has_mobile = !frappe.meta.has_field || frappe.meta.has_field(doctype, "mobile_no");
    let has_phone = !frappe.meta.has_field || frappe.meta.has_field(doctype, "phone");

    variants.forEach(v => {
        if (v) {
            if (has_mobile) or_filters.push(["mobile_no", "like", "%" + v + "%"]);
            if (has_phone) or_filters.push(["phone", "like", "%" + v + "%"]);
        }
    });

    if (or_filters.length === 0) {
        frappe.msgprint({
            title: __("Validation Error"),
            message: __("Cannot check duplicate phone: No 'phone' or 'mobile_no' field in Doctype '{0}'", [doctype]),
            indicator: "red"
        });
        return Promise.reject();
    }

    return new Promise((resolve, reject) => {
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: doctype,
                or_filters: or_filters,
                fields: ["name", doctype === "Customer" ? "customer_name" : "name"]
            },
            callback: function(r) {
                if (r.message && r.message.length > 0) {
                    const existing = r.message[0];
                    let display_name = existing.customer_name || existing.name;
                    frappe.msgprint({
                        title: __("Duplicate Mobile Number"),
                        message: __("Mobile number {0} already exists for {1}: {2}", 
                            [mobile_no, doctype.toLowerCase(), display_name]),
                        indicator: "orange"
                    });
                    reject();
                } else {
                    resolve();
                }
            },
            error: function() {
                reject();
            }
        });
    });
};
