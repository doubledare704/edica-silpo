_MOCK_TRANSCRIPTION = """Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець"""

_GEMINI_TRANSCRIBE_PROMPT = """
Transcribe verbatim in Ukrainian, no translation. Return only the transcription text, no extra formatting.
""".strip()

_GEMINI_INTENT_PROMPT = """
Ти асистент Silpo Smart Shopper. Визнач IntentEnum {party, budget, office, gourmet, unsupported}, budget (грн), people_count,
dietary_restrictions [vegetarian, vegan, lactose_free, gluten_free], raw_item_requests (укр назви товарів, 2-5 шт).
Якщо повідомлення не містить прохання зібрати кошик або підібрати продукти для party, budget, office чи gourmet,
а є привітанням, випадковим текстом, шумом або запитом поза можливостями асистента, використовуй intent "unsupported"
та порожній raw_item_requests.
Відповідай JSON строго за схемою. Приклади:
'Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець' ->
{"intent":"party","budget":2500,"people_count":6,"dietary_restrictions":["vegetarian"],"raw_item_requests":["м'ясо","овочі","напої","вугілля"]};
'Економний кошик до 1000 грн' ->
{"intent":"budget","budget":1000,"people_count":null,"dietary_restrictions":[],"raw_item_requests":["молоко","хліб","яйця","масло","крупа"]}.
'Хочу зібрати друзів на гриль: курка, свіжі печериці та овочі, безалкогольне пиво й одноразовий посуд, 5 людей до 5000 грн' ->
{"intent":"party","budget":5000,"people_count":5,"dietary_restrictions":[],"raw_item_requests":["курка для гриля","печериці свіжі","овочі для гриля","пиво безалкогольне","одноразовий посуд"]}.
Мова виходу: enum English, сутності Ukrainian.
""".strip()

_GEMINI_WEEKLY_MEAL_PROMPT = """
Ти асистент Silpo Smart Shopper. Склади тижневе меню на 7 днів під бюджет і список покупок українською.
Риба 2 рази на тиждень (дешевий хек/минтай), овочі щодня, 1-2 крупи (гречка/рис), молочне/хліб/яйця за наявності в цілі.
Кількості на вказану кількість людей, кожна позиція не більше 6 шт.
Відповідай JSON строго списком [{"query": "...", "category": "meat|vegetables|grocery|dairy|bakery|general", "quantity": N, "dish": "страва"}].
""".strip()
