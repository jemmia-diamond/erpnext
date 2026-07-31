import re
import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException

def normalize_to_standard_format(phone: str, default_country: str = "VN") -> str:
    if not phone:
        return ""

    # 1. Try parsing with phonenumbers
    try:
        parsed = phonenumbers.parse(phone, default_country)
        if phonenumbers.is_valid_number(parsed):
            formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            return formatted.replace("+", "")
    except NumberParseException:
        pass

    # 2. Fallback logic: extract digits only
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return ""

    # Get country code safely
    try:
        country_code = str(phonenumbers.country_code_for_region(default_country))
    except Exception:
        country_code = "84"

    # Rule A: starts with '0' (e.g., '0901234567' -> '84901234567')
    if digits.startswith("0") and len(digits) >= 9:
        return country_code + digits[1:]

    # Rule B: starts with '840' (e.g., '840901234567' -> '84901234567')
    if digits.startswith(country_code + "0") and len(digits) >= len(country_code) + 9:
        return country_code + digits[len(country_code) + 1:]

    return digits

def is_valid_phone_number(phone: str, default_country: str = "VN") -> bool:
    if not phone or not str(phone).strip():
        return False
    phone_str = str(phone).strip()
    try:
        parsed = phonenumbers.parse(phone_str, default_country)
        if phonenumbers.is_valid_number(parsed):
            return True
    except Exception:
        pass

    if not phone_str.startswith("+"):
        try:
            parsed = phonenumbers.parse("+" + phone_str)
            if phonenumbers.is_valid_number(parsed):
                return True
        except Exception:
            pass

    return False

def get_phone_variants(phone: str, default_country: str = "VN") -> list:
    """Generate different formatting variants of a phone number for DB search."""
    if not phone:
        return []

    variants = set([phone])
    digits = re.sub(r"\D", "", phone)
    if digits:
        variants.add(digits)

    try:
        parsed = phonenumbers.parse(phone, default_country)
        if phonenumbers.is_valid_number(parsed):
            formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            variants.add(formatted.replace("+", ""))
            national_format = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
            national_digits = re.sub(r"\D", "", national_format)
            if national_digits:
                variants.add(national_digits)
    except NumberParseException:
        pass

    return list(variants)
