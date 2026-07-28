# Telegram rollout runbook

Цей runbook використовується тільки після deployment TP-1011. Він не містить
реальних bot token, webhook secret, chat ID, phone або customer payload.

## Передумови

- Раніше оприлюднений Telegram bot token відкликано через BotFather.
- Новий bot token створено поза репозиторієм.
- Окремий webhook secret згенеровано поза репозиторієм.
- Production CRM доступна через HTTPS `CRM_PUBLIC_URL`.
- У production вже deployed код і migrations TP-1010—TP-1011.

## Secret files

На production host зберігайте значення тільки у `/opt/podoria-crm/secrets`
з mode `0600` і власником production deployment user:

```text
telegram_bot_token
telegram_webhook_secret
```

Deployment environment має передати:

```dotenv
TELEGRAM_BOT_TOKEN_FILE=/run/secrets/telegram_bot_token
TELEGRAM_WEBHOOK_SECRET_FILE=/run/secrets/telegram_webhook_secret
TELEGRAM_BOT_USERNAME=podo_crm_pod_bot
CRM_PUBLIC_URL=https://crm.example.invalid
```

## Webhook setup

Після deployment виконайте з production backend container:

```sh
python manage.py configure_telegram_webhook
```

Для контрольованого першого запуску, коли потрібно відкинути старі pending
updates у Telegram:

```sh
python manage.py configure_telegram_webhook --drop-pending-updates
```

Команда:

- відмовляється працювати без token/secret;
- вимагає HTTPS `CRM_PUBLIC_URL`;
- виконує `getMe` і звіряє `TELEGRAM_BOT_USERNAME`;
- встановлює webhook із secret header;
- не друкує token або webhook secret.

## Smoke test

Використовуйте лише synthetic заявку без реальних клієнтських даних.

1. Підключіть одного admin і одного reception через CRM Telegram dialog.
2. Створіть synthetic booking request через documented integration API або
   контрольований backend shell без customer PII.
3. Переконайтеся, що обидва private chats отримали повідомлення.
4. Натисніть `✅ Оброблено` в одному чаті.
5. Переконайтеся, що CRM status став `Оброблена`, `processed_by` відповідає
   Telegram actor, а обидва Telegram messages оновились: action button зник,
   CRM link лишився.
6. Повторне натискання callback має показати already-processed response і не
   створити другий audit mutation.
7. Видаліть synthetic заявку/submission, якщо це дозволено тільки для
   контрольованих dev/staging даних; production customer data не чиститься
   ad hoc.

## Evidence hygiene

Evidence дозволяє:

- redacted command success/failure;
- `getMe` username без token;
- HTTP status codes;
- public booking request number;
- counts of deliveries/edits.

Evidence забороняє:

- bot token або webhook secret;
- Telegram chat/user IDs;
- phone, contact handle, message text або іншу customer PII;
- raw Telegram update payload.
