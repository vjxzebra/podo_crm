# TP-804 — role overview and admin analytics contract

Статус: frozen 2026-07-22. Packet є read-only і migration-free.

## 1. Межі

У scope входять:

- role-aware `/` для admin, reception і podologist;
- admin-only `/analytics`;
- server-derived projections із `Appointment`, `Visit`, `VisitServiceLine`, `Patient`, `Receivable`, `Payment`, `Refund`, `CashLedgerEntry`, `WorkItem`, `ClinicWorkday` і `ClinicBreak`;
- loading, empty, filter, error/retry та desktop/tablet/mobile states;
- reconciliation tests на контрольованому dataset.

Не входять: нові persistent aggregates, фоновий ETL, materialized views, forecast ML, branches, specialist-specific work schedules та export. Prototype export CTA у production не рендериться.

## 2. API

### `GET /api/v1/overview?date=YYYY-MM-DD`

Доступний кожному authenticated active user. `date` optional; default — поточна дата `Europe/Kyiv`.

Response містить:

- `role`, `date`, `timezone`;
- `metrics[]` із server-owned key/label/integer value/format/note/tone;
- role-scoped `schedule[]` за локальну календарну дату;
- `next_appointment` у межах вибраної дати або `null`;
- clinic-wide `workday` із start/end/break/net minutes;
- `attention[]` без заборонених object details.

Podologist отримує лише власні appointments/patients/schedule/next appointment і власні work-item attention counts. Finance keys у response фізично відсутні.

Reception отримує clinic appointment/patient schedule, net payments за день, кількість podologists у розкладі та open receivables.

Admin отримує clinic appointment/patient schedule, expected income за активними appointment services, podologists у розкладі й clinic attention counters. Expected income є оперативним forecast за поточною catalog price і не називається ledger revenue.

### `GET /api/v1/analytics?from=YYYY-MM-DD&to=YYYY-MM-DD&specialist_id=&service_id=`

Тільки admin. `from` і `to` inclusive у `Europe/Kyiv`; сервер перетворює їх на half-open UTC range `[from 00:00, to + 1 day 00:00)`. Range обов'язковий, `from <= to`, максимум 366 днів. Specialist повинен бути podologist; service — наявний catalog service. Inactive historical specialists/services залишаються валідними filters.

Response містить:

- normalized `period` і applied filters;
- available specialist/service options;
- KPI: completed visits, ledger revenue, average check, returning-patient rate, new served patients, canceled appointments, no-shows, average return interval;
- aligned daily/weekly/monthly `trend` buckets;
- appointment outcome counts;
- specialist performance;
- service ranking із completed line quantities та billed totals.

Зміна будь-якого filter виконує один новий server request і оновлює весь response; frontend не перераховує бізнес-метрики локально.

## 3. Формули

### Виторг

`revenue_minor = SUM(PAYMENT ledger.amount_minor) - SUM(REFUND ledger.amount_minor)` за `posted_at` у period. `DEPOSIT`/`WITHDRAWAL` не є виторгом. Specialist/service filters застосовуються через immutable payment → receivable → completed visit relation; refund успадковує scope original payment.

### Середній чек

`average_check_minor = revenue_minor / payment_count`, rounded to nearest minor unit. За відсутності payments значення `0`. Full refund зменшує numerator, але не стирає historical payment count.

### Візити та пацієнти

- completed visits фільтруються за `Visit.completed_at`;
- returning patient — distinct patient із completed visit у period і щонайменше одним completed visit до `from` у тому самому specialist/service scope;
- returning rate = returning patients / distinct served patients у basis points (`0..10000`);
- new served patient — distinct patient із completed visit у period, чий `Patient.created_at` потрапляє у period;
- average return interval — середнє число повних днів між попереднім completed visit та completed visit у period для наявних repeat pairs.

### Outcomes і rankings

- appointment outcome period визначається за appointment start у local range;
- `COMPLETED`, `CANCELED`, `NO_SHOW` мають окремі counters; решта — `OTHER`;
- service ranking використовує completed `VisitServiceLine.quantity` і immutable `line_total_minor`; це billed service total, не ledger revenue.

### Завантаження спеціаліста

Denominator — сума clinic-wide working minutes за днями period мінус configured breaks. Numerator — scheduled appointment minutes спеціаліста, крім `CANCELED`, у range. Значення clamped до `0..10000` basis points. Окремих specialist shifts, holidays або exceptions TP-804 не вигадує.

## 4. UI/RBAC

- `/analytics` і navigation item доступні лише admin; reception/podologist direct URL → safe redirect, API → `403`;
- overview не містить demo numbers або client role switcher;
- schedule/next appointment мають canonical links тільки в дозволені route/object scopes;
- analytics filters: month, quarter, year, custom inclusive range, specialist і service;
- charts мають text/table equivalents; color не є єдиним носієм значення;
- mobile filters і detail content не створюють page horizontal overflow; actionable controls мають щонайменше 44 px;
- error state показує correlation ID і retry; empty dataset не підміняється fake rows.

## 5. Gate

- exact role response-shape tests, включно з відсутністю finance keys у podologist response;
- admin/reception/podologist overview scope tests;
- analytics RBAC/date/filter validation;
- exact controlled-dataset reconciliation для ledger revenue, average check, visits, cohort, outcomes, service ranking та utilization;
- OpenAPI/generated TypeScript contracts;
- component/axe tests для overview та analytics;
- authenticated desktop/tablet/mobile browser evidence з clean console й no page overflow.
