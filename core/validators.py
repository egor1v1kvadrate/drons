import re

from config import MAX_SN_LENGTH


def sanitize_input(value: str) -> str:
    """Удаляет опасные символы (разделители CSV и переносы строк)."""
    if not isinstance(value, str):
        return ""
    return value.replace(";", "_").replace("\n", "").replace("\r", "").strip()


def validate_serial_number(sn: str) -> tuple[bool, str]:
    """Проверяет серийный номер. Возвращает (успех, сообщение об ошибке)."""
    if not sn:
        return False, "Поле не может быть пустым."

    if len(sn) > MAX_SN_LENGTH:
        return False, f"Длина номера превышает {MAX_SN_LENGTH} символов."

    # Разрешаем только буквы (латиница/кириллица), цифры, дефис и пробел
    if not re.match(r"^[\w\- ]+$", sn):
        return False, "Номер содержит недопустимые спецсимволы."

    return True, "OK"


def validate_drone_form(form_data: dict) -> tuple[bool, str]:
    """Проверяет сразу всю форму при регистрации."""
    for key, value in form_data.items():
        is_valid, msg = validate_serial_number(value)
        if not is_valid:
            return False, f"Ошибка в поле '{key}': {msg}"
    return True, "OK"
