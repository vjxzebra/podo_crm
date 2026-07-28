# API створення заявок на запис

Статус: реалізовано у TP-1009; endpoint і OpenAPI-схема входять до актуальної
збірки.

Production base URL:

```text
https://crm.rozhenko.km.ua/api/v1
```

## 1. Призначення

API приймає заявки на запис із server-side інтеграцій:

- Instagram;
- Facebook;
- сайт.

Це не browser API. Bearer token не можна додавати у JavaScript, HTML, GTM,
публічний WordPress theme/plugin config або mobile bundle. Browser form має
надсилати дані на власний backend сайту, а вже backend викликає CRM.

## 2. Отримання і ротація token

Admin CRM:

1. відкриває `Налаштування → Інтеграції`;
2. натискає `Згенерувати токен`;
3. копіює token із one-time dialog;
4. зберігає його у secret storage інтеграції.

CRM не може повторно показати token. Кнопка `Згенерувати новий` негайно
інвалідовує попередній. Після rotation усі integrations мають отримати нове
значення.

Цей token не є Telegram bot token.

## 3. Endpoint

```http
POST /api/v1/integrations/booking-requests
```

Required headers:

```http
Authorization: Bearer <BOOKING_REQUEST_API_TOKEN>
Idempotency-Key: <stable unique value>
Content-Type: application/json
Accept: application/json
```

`Idempotency-Key`:

- required;
- 1–128 символів;
- один логічний submit завжди повторюється з тим самим key;
- змінений payload потребує нового key.

Рекомендовано використовувати UUID v4 або стабільний ID lead/form submission.

## 4. Request body

```json
{
  "source": "WEBSITE",
  "client_name": "Ім'я клієнта",
  "phone": "+380000000000",
  "service": "Консультація подолога",
  "contact_handle": "",
  "message": "Хочу записатися у другій половині дня",
  "preferred_at": "2026-08-01T12:00:00+03:00",
  "external_reference": "site-form-123"
}
```

| Поле | Required | Тип | Правило |
|---|---:|---|---|
| `source` | так | string | `INSTAGRAM`, `FACEBOOK` або `WEBSITE` |
| `client_name` | ні | string | blank або після trim до 160 символів |
| `phone` | ні | string | blank або до 32 символів і має нормалізуватися у валідний телефон |
| `service` | ні | string | назва/snapshot вибраної послуги, до 160 символів |
| `contact_handle` | ні | string | username/profile handle, до 100 символів |
| `message` | ні | string | коментар клієнта, до 2000 символів |
| `preferred_at` | ні | ISO 8601 datetime/null | timestamp із timezone offset |
| `external_reference` | ні | string | opaque ID зовнішньої системи, до 160 символів |

Невідомі поля не ігноруються і повертають `422 validation_error`.

## 5. Приклади

### cURL

```bash
curl --request POST \
  --url https://crm.rozhenko.km.ua/api/v1/integrations/booking-requests \
  --header "Authorization: Bearer ${BOOKING_REQUEST_API_TOKEN}" \
  --header "Idempotency-Key: 9cf0e563-b8ce-4d79-84c8-0c3b49ebef47" \
  --header "Content-Type: application/json" \
  --data '{
    "source": "INSTAGRAM",
    "client_name": "Ім'\''я клієнта",
    "phone": "+380000000000",
    "service": "Консультація подолога",
    "contact_handle": "@client",
    "message": "Хочу записатися",
    "preferred_at": null,
    "external_reference": "ig-lead-123"
  }'
```

### JavaScript на server-side

```js
const response = await fetch(
  "https://crm.rozhenko.km.ua/api/v1/integrations/booking-requests",
  {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.BOOKING_REQUEST_API_TOKEN}`,
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: JSON.stringify({
      source: "WEBSITE",
      client_name: "Ім'я клієнта",
      phone: "+380000000000",
      service: "Консультація подолога",
      message: "Форма з сайту",
    }),
  },
);

if (!response.ok) {
  throw new Error(`CRM request failed with HTTP ${response.status}`);
}

const bookingRequest = await response.json();
```

`crypto.randomUUID()` потрібно створити один раз для form submission і повторно
використовувати під час network retry. Не генеруйте новий key на кожен retry.

## 6. Success response

Перший create: HTTP `201 Created`.

```json
{
  "id": "00000000-0000-0000-0000-000000000000",
  "public_number": "REQ-0123456789",
  "status": "NEW",
  "created_at": "2026-07-28T10:00:00Z"
}
```

Exact retry з тим самим key і payload: HTTP `200 OK` та header:

```http
Idempotent-Replayed: true
```

Retry повертає той самий `id`, `public_number` і `created_at`; друга заявка не
створюється і Telegram delivery не дублюється.

## 7. Error response

Canonical format:

```json
{
  "code": "validation_error",
  "message": "Дані запиту не пройшли перевірку.",
  "fields": {
    "phone": [
      "Укажіть коректний номер телефону."
    ]
  },
  "correlation_id": "request-id"
}
```

| HTTP | `code` | Причина / дія |
|---:|---|---|
| `401` | `invalid_bearer_token` | token відсутній, malformed, invalid або rotated; перевірити secret |
| `409` | `idempotency_payload_mismatch` | key уже використано з іншим body; створити новий key |
| `422` | `idempotency_key_required` | додати stable `Idempotency-Key` |
| `422` | `validation_error` | виправити exact fields |
| `429` | `rate_limit_exceeded` | повторити після секунд із `Retry-After` |
| `500` | `internal_error` | retry з тим самим Idempotency-Key; передати support `correlation_id` |
| `503` | `service_unavailable` | retry з тим самим Idempotency-Key |

Для network timeout або невідомого `5xx` безпечно повторюйте exact request із тим
самим `Idempotency-Key`.

## 8. Security checklist інтегратора

- token зберігається лише у server-side secret manager/env;
- production і test tokens не збігаються;
- Authorization header не логуються;
- request/response body з phone/message не записуються у public logs;
- HTTPS certificate перевіряється;
- client має timeout і bounded retry;
- retry поважає `Retry-After`;
- rotation виконується контрольовано, після чого старий token видаляється;
- token не є параметром URL і не надсилається query string;
- приклади/bug reports використовують placeholder phone/message/token.

## 9. OpenAPI

Machine-readable schema:

```text
GET https://crm.rozhenko.km.ua/api/v1/schema
```

Operation використовує security scheme `bookingRequestBearerAuth`.
