from app.utils.speech import format_ukrainian_speech_text, number_to_ukrainian_words


def test_number_to_ukrainian_words_edges() -> None:
    assert number_to_ukrainian_words(0) == "нуль"
    assert number_to_ukrainian_words(1) == "один"
    assert number_to_ukrainian_words(12) == "дванадцять"
    assert number_to_ukrainian_words(34) == "тридцять чотири"
    assert number_to_ukrainian_words(100) == "сто"
    assert number_to_ukrainian_words(500) == "п'ятсот"
    assert number_to_ukrainian_words(1000) == "одна тисяча"
    assert number_to_ukrainian_words(2450) == "дві тисячі чотириста п'ятдесят"
    assert number_to_ukrainian_words(-15) == "мінус п'ятнадцять"


def test_format_ukrainian_speech_text_cleans_markdown() -> None:
    text = "Кошик **#1** на 3 осіб [посилання]"
    formatted = format_ukrainian_speech_text(text)
    assert "**" not in formatted
    assert "#" not in formatted
    assert "[" not in formatted
    assert "три" in formatted
