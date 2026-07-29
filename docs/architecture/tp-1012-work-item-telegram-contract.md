# TP-1012 — Telegram-сповіщення про призначені справи

Статус контракту: `frozen` 2026-07-29.

Джерело: погоджений запит власника продукту від 2026-07-29.

## 1. Мета і межа

Працівник, якому призначили внутрішню справу, отримує її у власний
підключений private Telegram chat. Повідомлення показує актуальний стан справи
та дозволяє:

- виконати відкриту справу кнопкою `✅ Виконати справу`;
- відкрити точну справу у CRM кнопкою `Відкрити в CRM`.

PostgreSQL лишається authoritative джерелом. Telegram-повідомлення є
best-effort проєкцією: помилка Telegram не відкочує створення, зміну,
перепризначення або завершення справи у CRM.

Цей packet розширює наявну TP-1010—TP-1011 Telegram-інфраструктуру і не змінює
заморожений контракт доставки нових заявок admin/reception.

## 2. Ролі й адресація

Усі active CRM users зі scope `work-items` можуть підключити власний Telegram:

- admin;
- reception;
- podologist.

Нова або перепризначена відкрита справа доставляється лише enabled
subscription поточного `assignee`. Інші працівники, включно з автором справи й
admin, окрему копію не отримують, якщо вони не є відповідальними.

Заявки на запис і надалі надсилаються лише ролям зі scope
`booking-requests`, тобто admin/reception.

## 3. Проєкція справи

Повідомлення містить:

- назву;
- один зі станів `🟡 Відкрита`, `🔴 Прострочена`, `✅ Виконана` або
  `↪️ Перепризначено`;
- тип;
- локальні дату й час терміну;
- ознаку важливості;
- безпечну назву та public number пацієнта або `Без пацієнта`;
- коментар із transport-safe обмеженням довжини;
- для виконаної справи — виконавця й час виконання;
- для старого відповідального — нового відповідального.

Телефон, Telegram identifiers, internal user ID та інші зайві персональні або
службові дані в текст не додаються.

`Відкрити в CRM` веде на:

```text
{CRM_PUBLIC_URL}/work-items?item={work_item_uuid}
```

CRM виконує власну session/RBAC перевірку; URL не є авторизаційним механізмом.

## 4. Delivery lifecycle

`WorkItemTelegramDelivery` є durable outbox/projection row:

- одна delivery на `(work_item, subscription)`;
- snapshot private `chat_id` і nullable Telegram `message_id`;
- `PENDING`, `SENT`, `RETRY`, `PERMANENT_FAILURE`;
- retry/backoff і sanitized transport error;
- остання синхронізована версія справи;
- окрема ознака синхронізованого overdue-стану.

Створення й зміна справи записують або актуалізують delivery у тій самій
database transaction. Broker enqueue виконується після commit; періодичний
dispatcher раз на хвилину підбирає пропущені pending/retry/stale rows.

При підключенні Telegram існуючі відкриті справи цього працівника додаються до
outbox, тому підключення не втрачає backlog.

## 5. Синхронізація станів

- Перехід терміну без зміни версії редагує sent message з `Відкрита` на
  `Прострочена`.
- Завершення у CRM або Telegram редагує message на `Виконана`, додає
  виконавця/час і прибирає кнопку завершення.
- Повторне відкриття повертає актуальний open/overdue стан і кнопку завершення.
- Перепризначення редагує стару копію на `Перепризначено` без кнопок і створює
  delivery для нового відповідального.
- Видалене message, blocked bot або недоступний Telegram не блокують доменну
  операцію; помилка ізолюється в exact delivery/subscription.

## 6. Callback і безпека

Callback має compact формат:

```text
wi:c:{work_item_uuid}
```

Перед завершенням backend перевіряє:

- verified webhook і deduplicated Telegram update;
- private chat;
- exact enabled subscription за `chat_id` і `telegram_user_id`;
- active CRM user зі scope `work-items`;
- користувач досі є поточним `assignee`.

Authorized callback викликає наявний `update_work_item` з optimistic version,
row lock, audit і звичайними domain permissions. Concurrent уже виконана справа
повертає safe already-completed result без другої mutation. Unauthorized і
невідомі callbacks не розкривають існування або вміст справи.

## 7. Не входить

- Telegram groups/channels;
- окреме планування або редагування справи в Telegram;
- призначення іншого відповідального з Telegram;
- гарантія редагування видаленого message або заблокованого chat;
- push до непідключеного користувача;
- production deployment без окремої команди власника.
