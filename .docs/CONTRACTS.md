# Test Contracts & Fixtures

## 1. Input Audio / Text Fixtures

```json
{
  "user_text": "Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець",
  "thread_id": "test-session-123"
}
```

## 2. Parsed Intent Output (parse_intent_node)

```json
{
  "intent": "party",
  "budget": 2500.0,
  "people_count": 6,
  "dietary_restrictions": ["vegetarian"],
  "raw_item_requests": ["м'ясо", "овочі", "напої", "вугілля"]
}
```

## 3. Mock MCP Response (mcp_fetch_node)

```json
[
  {"id": "sku-1", "title": "Ошийник свинячий", "price": 240.0, "is_private_label": false},
  {"id": "sku-2", "title": "Овочі для гриля Премія", "price": 85.0, "is_private_label": true}
]
```

## 4. Final Node Complete SSE Payload (node_complete)

```json
{
  "node": "tts",
  "intent": "party",
  "total_price": 2450.0,
  "is_budget_exceeded": false,
  "cart_url": "https://silpo.ua/cart/share/mock_123",
  "summary": "Я зібрав кошик для пікніка на шість осіб і вклався у дві тисячі чотириста п'ятдесят гривень.",
  "audio_url": "/static/audio/mock_response.mp3"
}
```

