import re


class InvalidPhoneError(ValueError):
    pass


def phone_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def normalize_phone(value: str) -> str:
    raw = value.strip()
    digits = phone_digits(raw)
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith("0"):
        digits = f"38{digits}"
    elif len(digits) == 11 and digits.startswith("80"):
        digits = f"3{digits}"
    if not 10 <= len(digits) <= 15:
        raise InvalidPhoneError("Укажіть номер телефону з 10–15 цифр.")
    return f"+{digits}"
