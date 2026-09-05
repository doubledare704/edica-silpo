_MOCK_TRANSCRIPTION = """Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець"""

_GEMINI_TRANSCRIBE_PROMPT = """
Transcribe verbatim in Ukrainian, no translation. Return only the transcription text, no extra formatting.
""".strip()

_GEMINI_INTENT_PROMPT = """
Ти асистент Silpo Smart Shopper. Визнач IntentEnum {party, budget, office, gourmet}, budget (грн), people_count,
dietary_restrictions [vegetarian, vegan, lactose_free, gluten_free], raw_item_requests (укр назви товарів, 2-5 шт).
Відповідай JSON строго за схемою. Приклади:
'Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець' ->
{"intent":"party","budget":2500,"people_count":6,"dietary_restrictions":["vegetarian"],"raw_item_requests":["м'ясо","овочі","напої","вугілля"]};
'Економний кошик до 1000 грн' ->
{"intent":"budget","budget":1000,"people_count":null,"dietary_restrictions":[],"raw_item_requests":["молоко","хліб","яйця","масло","крупа"]}.
Мова виходу: enum English, сутності Ukrainian.
""".strip()
