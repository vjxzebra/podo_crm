# TP-1014—TP-1021 — контракт допрацювань CRM

- Статус контракту: `frozen`
- Дата фіксації: `2026-08-06`
- Джерело: погоджені власником продукту правила та
  [план AI-розробки](../planning/tp-1014-1021-ai-development-plan.md).

## 1. Мета, межа та пріоритет контракту

Цей документ заморожує implementation contract для восьми пов'язаних пакетів:

- TP-1014 — кілька послуг у наступному записі з завершення прийому;
- TP-1015 — порожнє рукописне поле рекомендованої дати у PDF;
- TP-1016 — одна спільна каса клініки та перенесення фактичного залишку;
- TP-1017 — персональна доставка внутрішніх сповіщень у Telegram;
- TP-1018 — каталог знижок і налаштування loyalty policy;
- TP-1019 — кожен N-й новий завершений візит і canonical visit pricing;
- TP-1020 — атомарна заміна знижки рецепцією під час оплати;
- TP-1021 — інтеграційний release gate усього scope.

Якщо старі документи містять інше припущення саме для цього scope, цей контракт
має пріоритет. Незмінені частини попередніх контрактів продовжують діяти.
Production deployment не дозволений цим документом і потребує окремої команди.

## 2. Заморожені продуктові рішення

### 2.1. Каса

- У клініці є одна фізична каса `main`.
- На всю клініку одночасно існує не більше однієї `OPEN` касової зміни.
- Працівник, який відкрив зміну, є її owner і проводить усі payment, refund,
  deposit та withdrawal операції протягом дня.
- Інший працівник рецепції бачить owner відкритої зміни, але не може відкрити
  другу зміну або проводити owner-only операції.
- Наступну зміну після закриття може відкрити інший працівник рецепції.
- Початок першої нової зміни дорівнює `0`.
- Початок кожної наступної нової зміни дорівнює committed фактичній сумі,
  перерахованій при закритті останньої зміни, незалежно від її owner.
- Перенесений залишок не є виторгом, внесенням або ledger-операцією.
- Ручне введення opening balance не підтримується.

### 2.2. Loyalty та знижки

- Автоматична знижка діє на кожен N-й врахований візит: при `N = 5` — на
  5-й, 10-й, 15-й тощо.
- Візити, завершені до запуску програми, не враховуються і не backfill-яться.
- Рахуються лише нові успішно завершені візити під час активної policy.
- Draft, canceled, no-show, failed finish та idempotent replay не змінюють
  loyalty counter.
- Під час вимкненої policy counter не змінюється; повторне ввімкнення продовжує
  попередній прогрес.
- Зміна N або відсотка не скидає накопичений progress.
- N-й бонус вважається використаним навіть тоді, коли подолог або рецепція
  замінили loyalty-знижку іншою; бонус не переноситься.
- Допустимий відсоток — ціле число `1..99`; 100% не підтримується.
- На прийомі може діяти не більше однієї знижки; stacking заборонений.
- Подолог може встановити активну ручну знижку під час finish або замінити нею
  автоматичну loyalty-знижку.
- Рецепція може встановити активну ручну знижку під час payment або замінити
  нею поточну знижку.
- Знижку можна залишити або замінити іншою активною. Перехід
  `discount -> none` не входить у scope.
- Після settlement pricing і фінансові snapshots незмінні.

### 2.3. Telegram та PDF

- Telegram дублює внутрішній `Notification` лише його exact `recipient`.
- Broadcast admin/reception або будь-якій іншій ролі за самим kind заборонений.
- Telegram delivery не змінює `Notification.read_at` і не відкочує доменну
  операцію при transport failure.
- `work_item_overdue` не дублюється, бо його Telegram lifecycle уже належить
  delivery каналу справ.
- PDF-квитанція завжди містить порожнє місце для запису рекомендованої дати
  ручкою. Дата не зберігається у CRM і не заповнюється автоматично.

## 3. Ролі та RBAC

| Дія | ADMIN | RECEPTION | PODOLOGIST |
|---|---:|---:|---:|
| Завершити доступний прийом і створити follow-up | Так | Ні | Так, лише власний прийом |
| Обрати ручну знижку під час finish | Так | Ні | Так, лише власний прийом |
| Переглянути active discount picker | Так | Так | Так |
| Переглянути active/inactive каталог | Так | Ні | Ні |
| Створити, редагувати, деактивувати знижку | Так | Ні | Ні |
| Переглянути або змінити loyalty policy | Так | Ні | Ні |
| Відкрити касову зміну | Так | Так | Ні |
| Побачити поточну global OPEN shift | Так | Так | Ні |
| Провести payment/refund/deposit/withdrawal | Лише як owner | Лише як owner | Ні |
| Закрити зміну | Owner або чинний admin override | Лише owner | Ні |
| Завантажити/друкувати квитанцію | Так | Так | Ні |

Звичайний користувач не може розширити object scope через UUID або query
parameter. Недоступний та невідомий UUID мають однакову safe-not-found
семантику там, де це вже вимагають finance/visit контракти.

Telegram отримує лише користувач, який одночасно:

1. є active exact `Notification.recipient`;
2. має active private-chat `TelegramSubscription`;
3. має `subscription.user_id == notification.recipient_id`.

## 4. API contract

Усі JSON mutation bodies є strict: невідомі поля повертають `422`. Усі UUID
валідуються до domain lookup. Суми передаються цілими minor units.

### 4.1. Завершення прийому та multi-service follow-up

Чинний endpoint не змінюється:

```text
POST /api/v1/visits/{visit_id}/finish
Idempotency-Key: <stable non-empty key, max 128>
```

Relevant request shape:

```json
{
  "version": 4,
  "recommendations": "",
  "payment_handoff_requested": true,
  "discount_id": "manual-discount-uuid",
  "follow_up": {
    "starts_at": "2026-08-20T09:00:00+03:00",
    "service_ids": ["service-a-uuid", "service-b-uuid"],
    "specialist_id": 12,
    "room_id": "room-uuid"
  }
}
```

Правила `follow_up`:

- `follow_up = null` або omission означає не створювати наступний запис;
- canonical поле — `service_ids`, від 1 до 20 унікальних UUID;
- порядок `service_ids` є значущим і зберігається в
  `AppointmentServiceLine.position`;
- перша послуга стає legacy primary service appointment;
- усі послуги мають бути active на момент locked server validation;
- тривалість запису дорівнює сумі тривалостей усіх вибраних послуг;
- room і specialist availability перевіряються на весь сумарний інтервал;
- duplicate, empty, unknown або inactive service IDs повертають `422`;
- legacy `service_id` тимчасово підтримується як масив з одного елемента;
- одночасна передача `service_id` і `service_ids` повертає `422`;
- finish, service lines, inventory, receivable, pricing, recommendation,
  follow-up appointment та audit є однією транзакцією;
- exact idempotent replay повертає попередній result і не дублює appointment або
  service lines.

UI використовує повний active service catalog і спільний
`ServiceMultiSelect`. Початковий набір — активні послуги поточного прийому.
Зміна набору послуг анулює stale selected time, room та availability result.

`discount_id`:

- omission означає відсутність ручного override подолога;
- `null` не є командою очищення та не приймається;
- UUID має посилатися на active `Discount` під locked validation;
- manual selection замінює automatic loyalty discount без stacking;
- response містить authoritative `pricing` projection.

### 4.2. Каталог знижок

```text
GET  /api/v1/discounts?status=active|inactive|all
POST /api/v1/discounts
GET  /api/v1/discounts/{discount_id}
PATCH /api/v1/discounts/{discount_id}
```

`GET /discounts` доступний усім authenticated ролям. Для non-admin сервер
ігнорує спробу розширити scope і повертає лише active rows. Admin може
фільтрувати `active`, `inactive` або `all`.

Create request:

```json
{
  "name": "Постійний клієнт 10%",
  "percent": 10,
  "is_active": true
}
```

Patch request:

```json
{
  "version": 3,
  "name": "Постійний клієнт 12%",
  "percent": 12,
  "is_active": true
}
```

Інваріанти:

- `name` trim-иться, є non-empty та case-insensitive unique;
- `percent` — integer `1..99`;
- `version` positive і є optimistic concurrency precondition;
- patch містить щонайменше одну зміну крім `version`;
- physical delete заборонений; `is_active=false` є деактивацією;
- inactive discount не можна застосувати до нового finish/payment;
- rename, percent change або deactivation не змінюють historical snapshots;
- create/update/deactivate/reactivate audit-яться;
- mutation endpoints є admin-only.

Stable conflicts включають `discount_name_conflict`, `stale_version` та
`discount_used_by_active_loyalty` для недопустимої деактивації знижки, яку
використовує active policy.

### 4.3. Loyalty policy

```text
GET   /api/v1/loyalty-policy
PATCH /api/v1/loyalty-policy
```

Обидві операції admin-only. Існує одна policy з key `default`.

```json
{
  "version": 2,
  "is_active": true,
  "every_n": 5,
  "discount_id": "discount-uuid"
}
```

- `every_n` — integer `1..10000`;
- active policy потребує active `discount_id`;
- `discount_id=null` дозволений лише у configuration, яка після mutation не є
  active;
- optimistic conflict повертає `409 stale_version`;
- `started_at` встановлюється при першій активації та надалі не переписується;
- редагування policy не скидає `PatientLoyaltyState` і не змінює historical
  `VisitLoyaltyEvent` або `VisitPricing`.

### 4.4. Касові зміни

Чинні endpoint paths зберігаються:

```text
POST /api/v1/cash-shifts
GET  /api/v1/cash-shifts/current
GET  /api/v1/cash-shifts
GET  /api/v1/cash-shifts/{shift_id}
GET  /api/v1/cash-shifts/{shift_id}/close-preview
POST /api/v1/cash-shifts/{shift_id}/close
```

`POST /cash-shifts` не приймає opening amount. Під lock singleton drawer сервер:

1. відхиляє відкриття, якщо вже існує global `OPEN` shift;
2. знаходить останню committed `CLOSED` shift `main`;
3. створює `INITIAL` з opening `0`, якщо історичної closed shift немає;
4. інакше створює `CARRY_FORWARD`, де opening дорівнює
   `source.actual_cash_at_close_minor`.

`GET /cash-shifts/current` повертає global open shift, а не лише shift actor.
Projection додає:

```json
{
  "drawer_key": "main",
  "opening_cash_minor": 124500,
  "opening_basis": "CARRY_FORWARD",
  "opening_source_shift": {
    "id": "source-shift-uuid",
    "public_number": "CSH-..."
  },
  "permissions": {
    "can_mutate": false,
    "can_close": false
  }
}
```

Інший reception бачить owner і opening projection, але `can_mutate=false` і
`can_close=false`. Admin override close зберігає фактичного closer snapshot,
але не надає admin права проводити ledger operations у чужій зміні.

Close request, idempotency та stale preview rules лишаються визначеними
[TP-704](tp-704-cash-shift-close-history-contract.md). Authoritative formula
після TP-1016:

```text
expected_cash_minor = opening_cash_minor
                    + cash_payments_minor
                    - cash_refunds_minor
                    + deposits_minor
                    - withdrawals_minor
```

Opening входить у expected/available cash, але не входить у revenue,
deposits, payment totals або operations count. Історія, detail, audit і CSV
показують basis/source/opening; export не сумує expected balances як cash flow.

### 4.5. Payment із versioned discount action

Чинний endpoint:

```text
POST /api/v1/payments
Idempotency-Key: <stable non-empty key, max 128>
```

Canonical strict body використовує flat discriminated action:

```json
{
  "visit_id": "visit-uuid",
  "payment_method": "CASH",
  "comment": "",
  "pricing_version": 1,
  "discount_action": "KEEP"
}
```

або:

```json
{
  "visit_id": "visit-uuid",
  "payment_method": "CARD",
  "comment": "",
  "pricing_version": 1,
  "discount_action": "SET",
  "discount_id": "discount-uuid"
}
```

Validation matrix:

| `discount_action` | `discount_id` | Результат |
|---|---|---|
| `KEEP` | omitted | Зберегти current pricing |
| `KEEP` | present | `422` |
| `SET` | active UUID | Встановити або замінити одну знижку |
| `SET` | omitted/null | `422` |
| `SET` | inactive/unknown UUID | `409 discount_unavailable` без existence leak |
| `CLEAR` або інше | будь-яке | `422` unsupported action |

В одній transaction service:

1. перевіряє exact idempotent replay;
2. lock-ить owner global `OPEN` cash shift, receivable і `VisitPricing` у
   canonical lock order;
3. перевіряє `pricing_version`, `OPEN` pricing та unpaid receivable;
4. для `SET` під lock читає active discount і server-side перераховує pricing;
5. синхронно змінює `Visit.total_minor`, `Receivable.amount_minor` і pricing net;
6. створює один ledger entry та один immutable `Payment` на net amount;
7. переводить receivable у `PAID`, pricing у `SETTLED` та фіксує snapshots;
8. пише audit і idempotency result атомарно.

Stale `pricing_version` повертає recoverable `409 pricing_version_conflict` і
не залишає mutation. Exact replay повертає той самий final snapshot. Інший
payload із тим самим key повертає `409 idempotency_payload_mismatch`.

Після payment жоден endpoint, model save або raw SQL не може змінити settled
pricing. Refund використовує actual net amount із Payment/Ledger і не
перераховує поточний каталог знижок.

## 5. Модель даних та інваріанти

### 5.1. `CashDrawer` і `CashShift`

`CashDrawer` є singleton row з immutable key `main`. `CashShift` містить:

- protected FK `drawer`;
- immutable `opening_cash_minor`;
- immutable nullable self-FK `opening_source_shift` з `PROTECT`;
- immutable `opening_basis`: `LEGACY | INITIAL | CARRY_FORWARD`;
- owner `employee` та чинні immutable opener/closer snapshots.

Database guards забезпечують:

- partial unique: одна `OPEN` shift на drawer;
- unique non-null source: одна closed shift не переноситься двічі;
- source не посилається на себе;
- `LEGACY`: лише pre-cutover, opening `0`, source `NULL`;
- `INITIAL`: лише перша post-cutover shift без попередньої closed, opening `0`,
  source `NULL`;
- `CARRY_FORWARD`: source є останньою closed shift того самого drawer, opening
  дорівнює її committed actual;
- opening/source/basis не змінюються після insert;
- lifecycle та ledger triggers включають opening у expected і available cash;
- closed shift та posted ledger rows залишаються immutable.

### 5.2. `NotificationTelegramDelivery`

Durable outbox row містить:

- protected FK `notification` і `subscription`;
- snapshot private `chat_id`, nullable Telegram `message_id`;
- `PENDING | SENT | RETRY | PERMANENT_FAILURE`;
- `attempt_count`, `next_attempt_at`, sanitized `error_code/error_message`;
- timestamps;
- unique `(notification, subscription)`.

Notification creation best-effort створює delivery для exact enabled
subscription після committed domain mutation. Broker enqueue відбувається
on-commit; periodic dispatcher щохвилини підбирає пропущені pending/retry rows.
Workers використовують row locks/`skip_locked`, тому concurrent dispatch не
надсилає дві успішні копії одного row.

Payload містить лише title, message, локальний occurred time і safe CRM link.
Link формується з валідного `CRM_PUBLIC_URL` та relative `Notification.deep_link`;
невалідний link не додається. Token, chat ID та internal recipient ID не
потрапляють у message або tracked evidence. Transport error санітизується.

### 5.3. `Discount` і `LoyaltyPolicy`

`Discount` містить UUID, name, percent, active flag, version і timestamps.
Відсоток та unique normalized name захищені на application і database рівнях.
Delete заборонений; historical FK використовують `PROTECT`.

`LoyaltyPolicy` є singleton `default`: active flag, `every_n`, protected
discount FK, version, immutable first `started_at` і timestamps. Active policy
без configured active discount невалідна.

### 5.4. `PatientLoyaltyState` і `VisitLoyaltyEvent`

`PatientLoyaltyState`:

- one-to-one з patient;
- `completed_count >= 0`;
- створюється lazy лише при успішному finish під active policy;
- не формується з historical visits;
- змінюється лише locked finish service.

`VisitLoyaltyEvent`:

- one-to-one з visit;
- unique `(patient, sequence_number)`;
- positive sequence та `every_n_snapshot`;
- `eligible = sequence_number % every_n_snapshot == 0`;
- immutable snapshots policy start, N, automatic discount name/percent;
- append-only і створюється рівно один раз успішним finish, коли policy active.

Event фіксує використання N-го бонусу до manual override. Тому заміна discount
не видаляє eligibility і не переносить бонус.

### 5.5. `VisitPricing`

Для кожного finished visit існує рівно один pricing row:

- one-to-one protected visit;
- immutable `gross_minor`;
- nullable protected discount FK;
- immutable-at-settlement name/percent/source snapshots;
- source `LOYALTY | PODOLOGIST | RECEPTION` або empty для no discount;
- nullable `applied_by` для ручного вибору;
- `discount_amount_minor`, `net_minor`, positive `version`;
- state `OPEN | SETTLED` і nullable `settled_at`.

Canonical arithmetic виконується тільки server-side:

```text
gross_minor = sum(immutable service line totals)
discount_amount_minor = gross_minor * percent // 100
net_minor = gross_minor - discount_amount_minor
```

No-discount pricing має null discount/percent/applied_by, empty name/source,
discount amount `0` і `gross == net`. Для `gross_minor = 0` знижка не
застосовується: loyalty ordinal за active policy все одно споживається, але
pricing є no-discount, `Visit.total_minor = Receivable.amount_minor = 0`,
receivable одразу `PAID`, pricing одразу `SETTLED`, Payment і ledger row не
створюються.

Завжди виконується:

```text
Visit.total_minor
  == Receivable.amount_minor
  == VisitPricing.net_minor
```

`total_minor` лишається backward-compatible net projection. Revenue, payments
і refunds використовують net; service-volume analytics — gross immutable line
totals; discount analytics — окремі snapshots.

### 5.6. Payment snapshots

Payment лишається append-only і, крім чинних identity/service snapshots,
фіксує pricing на момент settlement:

- gross amount;
- discount catalog ID, name, percent і source або canonical no-discount values;
- discount amount;
- net amount;
- `visit_total_minor_snapshot` як backward-compatible net.

Rename, percent edit або deactivation `Discount` після оплати не змінює Payment,
receipt, refund чи historical finance projections.

## 6. Transaction та concurrency contract

### 6.1. Finish

Canonical lock order документується в service tests і однаковий для всіх
finish paths: appointment/visit/patient, policy/loyalty state, discount,
inventory resources, потім dependent writes. До counter increment service
перевіряє exact idempotent replay.

Під active policy locked finish:

1. lazy створює або lock-ить patient state;
2. збільшує counter рівно один раз;
3. створює immutable event з наступним unique sequence;
4. визначає automatic discount;
5. застосовує optional podologist override;
6. створює canonical pricing і receivable;
7. завершує visit, inventory, follow-up та audit в одній transaction.

Два concurrent finish різних visits одного patient отримують різні послідовні
ordinals. Rollback будь-якого dependent write відкочує counter/event/pricing.

### 6.2. Cash та payment

Open/close блокують singleton drawer. У race двох open лише один request
успішний. Close/open переносить лише committed actual; uncommitted або stale
actual ніколи не стає opening.

Payment/refund/withdrawal та close мають узгоджений lock order. Одночасні
withdrawal/refund на межі available cash не створюють від'ємний залишок.
Ledger insert проти close не залишає late entry.

Дві concurrent payment attempts, у тому числі з різними `SET` discounts,
дають рівно один Payment, один ledger row і один final settled pricing. Інший
request отримує idempotent replay або deterministic conflict без partial state.

## 7. PDF contract

Endpoint і базовий формат лишаються визначеними
[TP-1013](tp-1013-payment-receipt-pdf-contract.md):

```text
GET /api/v1/payments/{payment_id}/receipt?disposition=attachment|inline
```

На другій A4-сторінці після рекомендацій і перед підписами завжди друкується:

```text
Рекомендована дата наступного візиту: ____ / ____ / ______
```

- поле порожнє з рекомендаціями, без рекомендацій і після refund;
- жодна visit, appointment або system date не підставляється;
- поля БД чи API для цієї дати немає;
- документ лишається рівно двосторінковим A4.

Після TP-1020 перша сторінка показує gross, назву та percent знижки,
discount amount і net із Payment snapshots. Поточний каталог не читається для
historical receipt.

## 8. Telegram delivery contract

Нового public API endpoint немає. Розширюється domain hook створення
`Notification` з [TP-802](tp-802-notifications-contract.md).

- Для кожного нового eligible Notification шукається лише subscription exact
  recipient.
- Відсутній/disabled subscription або inactive recipient означає safe no-op.
- `work_item_overdue` пропускається, оскільки його доставка належить
  [TP-1012](tp-1012-work-item-telegram-contract.md).
- Duplicate enqueue/concurrent workers зводяться до одного delivery row.
- Transient failure переходить у `RETRY` з bounded exponential backoff або
  Telegram `retry_after`.
- Permanent transport failure переходить у `PERMANENT_FAILURE`; blocked bot
  може вимкнути exact subscription.
- Telegram failure не змінює Notification, `read_at` або source domain object.
- Live Bot API не викликається в automated tests.

## 9. Міграційна та rollout стратегія

Ризикові financial schema changes виконуються щонайменше у двох сумісних
етапах.

### 9.1. Expand + bridge

- Додати nullable/new schema та індекси без видалення legacy guards.
- Створити singleton drawer.
- Backfill усіх pre-cutover shifts як `drawer=main`, opening `0`, source null,
  basis `LEGACY`; historical reconciliation і ledger не змінювати.
- Поточну legacy OPEN shift не закривати автоматично; її actual після штатного
  close є source наступної зміни.
- Створити neutral pricing для кожного legacy receivable:
  `gross=net=old amount`, discount none, amount `0`;
  `PAID/REFUNDED -> SETTLED`, `OPEN -> OPEN`.
- Не створювати historical loyalty states/events.
- Додати notification delivery table без зміни старих notifications,
  subscriptions або work-item deliveries.
- Bridge image читає старі й нові rows; нові features вимкнені.

### 9.2. Contract + activate

- Перед mutation read-only preflight перевіряє `0..1` OPEN shift,
  reconciliation, orphan ledger/payment/refund та visit/receivable/payment
  totals.
- Більше однієї OPEN shift зупиняє migration до data mutation; система не
  обирає і не закриває shift автоматично.
- Під maintenance lock повторно backfill-яться bridge rows.
- Додаються NOT NULL, unique, check та PostgreSQL trigger guards для cash і
  pricing invariants.
- Лише після green compatibility gate вмикаються features.
- Previous deployable image має бути bridge image, сумісний із forward schema.

### 9.3. Rollback boundary

- Expand можна reverse-ити лише до появи нових records.
- Після першої carried-forward shift, loyalty event, discounted pricing або
  Payment pricing snapshot reverse migration заборонена.
- Rollback дозволений лише на перевірений bridge image.
- Якщо bridge image несумісний, потрібні maintenance mode та restore
  перевіреного recovery point на clean targets.
- Заборонено частково видаляти ledger/pricing/loyalty rows або переписувати
  closed financial facts.

На disposable PostgreSQL обов'язковий `old -> new -> old -> new` gate до
незворотної boundary, із порівнянням IDs, counts, amounts, snapshots та
constraints. Окремі migration scenarios покривають 0/1/2 OPEN shifts, legacy
pricing, no-loyalty-backfill і raw-SQL guards.

## 10. Stable failures та security invariants

Разом із чинними shared API errors контракт очікує:

- `409 cash_shift_already_open` для другої global OPEN shift;
- `409 cash_shift_changed` для stale close preview;
- `409 pricing_version_conflict` для stale payment pricing;
- `409 stale_version` для catalog/policy optimistic conflict;
- `409 discount_name_conflict` для duplicate normalized name;
- `409 idempotency_payload_mismatch` для reuse key з іншим payload;
- `409 discount_unavailable` для inactive/unknown catalog discount;
- `422` для `CLEAR`, stacking attempt, invalid percent та inconsistent action.

Database та application guards мають блокувати:

- другу OPEN shift навіть через raw SQL;
- post-cutover insert `LEGACY` або неправдивий `INITIAL`;
- зміну opening/source/basis;
- negative available cash або ledger insert у closed shift;
- discount percent поза `1..99`;
- більше однієї discount у pricing;
- невірну gross/discount/net formula;
- mutation settled pricing або Payment snapshots;
- розсинхронізацію Visit, Receivable, Pricing, Payment і Ledger net amounts.

У tracked files, fixtures та evidence заборонені real credentials, Telegram
token/chat ID і customer PII. Automated Telegram tests використовують fake
transport.

## 11. Acceptance gates

### TP-1014

- ordered 2+ service lines, primary та aggregate duration;
- empty/duplicate/inactive/unknown IDs;
- conflict у другій частині сумарного interval;
- stale selection reset, full transaction rollback, exact replay;
- follow-up arrival/start переносить усі service lines;
- component, keyboard та accessibility tests.

### TP-1015

- `pypdf`: рівно 2 A4 pages і label на page 2;
- поле є з/без recommendations і після refund;
- Poppler render без clipping/overlap/third page;
- повторна PDF перевірка після pricing rows TP-1020.

### TP-1016

- initial `0`, legacy grandfathering та cross-user actual carry-forward;
- одна global open race, close/open race і unique source;
- owner/non-owner/admin/podologist RBAC;
- expected/available formula, withdrawal/refund boundary;
- DB trigger/raw-SQL guards, audit/history/detail/CSV projections.

### TP-1017

- recipient A отримує, subscription B не отримує;
- inactive/unlinked recipient no-op;
- duplicate/concurrent enqueue та dispatch;
- transient retry, permanent failure, sanitized error та safe link;
- Notification/source operation не rollback-иться і `read_at` не змінюється;
- `work_item_overdue` не дублюється.

### TP-1018

- admin CRUD/deactivate/reactivate та audit;
- 1% і 99% valid; 0% і 100% invalid;
- normalized duplicate name і stale version conflicts;
- non-admin бачить тільки active picker;
- policy configuration/disable/re-enable без progress reset;
- responsive UI states та keyboard accessibility.

### TP-1019

- при N=5 automatic discount лише на 5-му та 10-му;
- old visits не рахуються;
- failed/replayed/inactive-policy finish не змінює counter;
- concurrent patient ordinals унікальні й послідовні;
- `none -> podologist manual` і `loyalty -> podologist manual` без stacking;
- N-й bonus споживається після override;
- inactive discount reject, immutable snapshots, rounding edge cases;
- gross zero одразу `PAID/SETTLED` без Payment/Ledger.

### TP-1020

- reception `KEEP`, `none -> SET` і `discount -> SET`;
- `CLEAR` та `discount -> none` reject;
- stale pricing recoverable refresh;
- concurrent payments дають один Payment/final pricing;
- payment-vs-refund, payment-vs-close та override races без partial state;
- ledger/refund/analytics/export/PDF використовують net;
- legacy no-discount records лишаються сумісними;
- settled pricing і snapshots immutable через ORM та raw SQL.

### TP-1021

Обов'язковий cross-feature scenario:

```text
4 нові завершені візити
-> 5-й візит із двома послугами
-> automatic loyalty discount
-> reception замінює її іншою active discount
-> net payment
-> двосторінкова PDF-квитанція з порожнім полем дати
-> owner закриває shift
-> інший reception відкриває наступну shift
-> opening дорівнює actual попередньої shift
```

Scenario додатково доводить відсутність stacking, правильний ordinal,
immutable snapshot після catalog edit і одну global open shift.

Фінальний gate включає fresh/populated migrations, Ruff, format, mypy, Django
checks, pytest, OpenAPI snapshot/validation, generated TypeScript client,
ESLint, strict TypeScript, Vitest, production build, desktop/tablet/mobile
browser verification, `0` serious/critical axe violations, PDF render і healthy
worker/beat/readiness probes.

## 12. Out of scope

- Production deployment без окремої команди.
- 100% discount, complimentary visit або write-off workflow.
- Сумування кількох знижок.
- Очищення вже застосованої знижки до `none`.
- Ретроактивні discount або loyalty backfill для старих visits.
- Перенесення невикористаного N-го бонусу.
- Кілька cash drawers або кілька одночасних cashier owners.
- Ручний opening balance.
- Reopen/edit/delete closed shift або posted financial facts.
- Збереження рекомендованої дати наступного візиту у БД/API.
- Автоматичне створення appointment із рукописної дати.
- Позначення Notification прочитаним через Telegram.
- Telegram groups/channels, broadcast або live Bot API у tests.
- РРО/ПРРО, fiscal receipt, accounting settlement або multi-currency.

## 13. Пов'язані контракти

- [Domain model](domain-model.md)
- [TP-704 — касові зміни](tp-704-cash-shift-close-history-contract.md)
- [TP-802 — внутрішні сповіщення](tp-802-notifications-contract.md)
- [TP-1012 — Telegram для справ](tp-1012-work-item-telegram-contract.md)
- [TP-1013 — PDF-квитанція](tp-1013-payment-receipt-pdf-contract.md)
