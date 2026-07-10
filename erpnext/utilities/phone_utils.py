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
