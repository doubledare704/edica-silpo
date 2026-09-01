import re

UNITS: dict[int, str] = {
    0: "нуль",
    1: "один",
    2: "два",
    3: "три",
    4: "чотири",
    5: "п'ять",
    6: "шість",
    7: "сім",
    8: "вісім",
    9: "дев'ять",
}

TEENS: dict[int, str] = {
    10: "десять",
    11: "одинадцять",
    12: "дванадцять",
    13: "тринадцять",
    14: "чотирнадцять",
    15: "п'ятнадцять",
    16: "шістнадцять",
    17: "сімнадцять",
    18: "вісімнадцять",
    19: "дев'ятнадцять",
}

TENS: dict[int, str] = {
    2: "двадцять",
    3: "тридцять",
    4: "сорок",
    5: "п'ятдесят",
    6: "шістдесят",
    7: "сімдесят",
    8: "вісімдесят",
    9: "дев'яносто",
}

HUNDREDS: dict[int, str] = {
    1: "сто",
    2: "двісті",
    3: "триста",
    4: "чотириста",
    5: "п'ятсот",
    6: "шістсот",
    7: "сімсот",
    8: "вісімсот",
    9: "дев'ятсот",
}


def _three_digits_to_words(n: int, *, feminine: bool = False) -> str:
    parts: list[str] = []
    hundreds_digit = n // 100
    tens_and_units = n % 100

    if hundreds_digit > 0:
        parts.append(HUNDREDS[hundreds_digit])

    if 10 <= tens_and_units <= 19:
        parts.append(TEENS[tens_and_units])
    else:
        tens_digit = tens_and_units // 10
        unit_digit = tens_and_units % 10

        if tens_digit > 0:
            parts.append(TENS[tens_digit])

        if unit_digit > 0:
            if feminine and unit_digit == 1:
                parts.append("одна")
            elif feminine and unit_digit == 2:
                parts.append("дві")
            else:
                parts.append(UNITS[unit_digit])

    return " ".join(parts)


def number_to_ukrainian_words(n: int) -> str:
    """Converts an integer to Ukrainian words (supports up to hundreds of thousands)."""
    if n < 0:
        return f"мінус {number_to_ukrainian_words(abs(n))}"
    if n == 0:
        return UNITS[0]

    parts: list[str] = []
    thousands = n // 1000
    remainder = n % 1000

    if thousands > 0:
        if thousands == 1:
            parts.append("одна тисяча")
        elif thousands == 2:
            parts.append("дві тисячі")
        elif thousands in (3, 4):
            parts.append(f"{UNITS[thousands]} тисячі")
        else:
            thousands_text = _three_digits_to_words(thousands, feminine=True)
            parts.append(f"{thousands_text} тисяч")

    if remainder > 0:
        parts.append(_three_digits_to_words(remainder, feminine=False))

    return " ".join(parts)


def format_ukrainian_speech_text(text: str) -> str:
    """Formats text for Respeecher TTS: plain text without markdown, numbers as Ukrainian words."""
    cleaned = re.sub(r"[\*\_\[\]\#\(\)]", "", text)

    def _replace_num(match: re.Match[str]) -> str:
        num = int(match.group(0))
        return number_to_ukrainian_words(num)

    formatted = re.sub(r"\b\d+\b", _replace_num, cleaned)
    return formatted.strip()
