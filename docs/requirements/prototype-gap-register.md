# Реєстр заглушок і невідповідностей прототипу Podoria CRM

## 1. Правило використання

`design/` є візуальним та інтерактивним орієнтиром, але не production-контрактом. Дані, дозволи, transitions і успішні toast-повідомлення у prototype не доводять наявність API, transaction, persistence або security.

Стани gap:

- `tracked` — має цільовий packet і перевіряється при його прийманні;
- `cross-cutting` — правило обов’язкове в кожному релевантному packet;
- `excluded` — демонстраційний елемент не входить у MVP без нового рішення;
- `resolved` — production implementation і tests уже усунули gap.

## 2. Канонічний реєстр

| ID | Evidence у prototype | Ризик / розбіжність | Цільове рішення | Owner / deadline packet | Стан |
|---|---|---|---|---|---|
| GAP-01 | `design/index.html:246`, `#recordRecommendations` | Recommendations є порожньою заглушкою попри SPEC §7.8 | Повний role-scoped список/редагування рекомендацій | Visits FE/BE + QA / TP-605 | `tracked` |
| GAP-02 | `design/index.html:271`, history tab має `data-finance-admin` | Reception не отримує власну історію shifts за SPEC §10.5 | Reception бачить тільки власні shifts; admin — усі | Billing FE/BE + QA / TP-704 | `tracked` |
| GAP-03 | Medical блоки існують у DOM і ховаються CSS | Дані можуть витекти через HTML/API навіть коли UI прихований | Окремі reception/medical serializers і selectors без заборонених keys | Patients BE + security / TP-302 | `resolved` 2026-07-21; reception serializer не має medical/photo keys, selector-level IDOR і negative serialization tests пройдені |
| GAP-04 | `design/assets/app.js:75,81,175`, `sessionStorage` і `#roleSwitcher` | Browser сам визначає роль і сесію | Production роль тільки із server session; switcher лише dev/storybook | Accounts FE/BE + security / TP-201 | `resolved` 2026-07-21; TP-201 session source + TP-203 team direct-URL evidence |
| GAP-05 | Більшість submit handlers змінюють `textContent`, `innerHTML` або масиви | Toast «збережено» не означає persistence, audit чи atomicity | Mutation лише через typed client → service layer → DB/audit → server response | Кожен domain owner / усі mutation packets | `cross-cutting` |
| GAP-06 | Prototype майже не має loading, server error, 409, offline, retry, unsaved | Happy-path demo приховує критичні recovery flows | ST-01—ST-16 із screen map у packet/component/e2e | Frontend + QA / кожен UI packet, фінал TP-901 | `cross-cutting` |
| GAP-07 | General settings не доводять повноту полів §17.1 | Можуть загубитися phone/email/address | Реалізувати повний clinic profile schema і form | Clinic FE/BE / TP-204 | `resolved` 2026-07-21; повний API/form contract + Edge evidence |
| GAP-08 | Prototype labels/rows не є стабільним status registry | Можливі зайві/відсутні статуси та неправильні переходи | Рівно 8 system codes, незмінні codes, configurable labels/colors/manual roles | Clinic + scheduling / TP-206, TP-403 | `in_progress`: TP-206 registry/protection/config UI done; transition table лишається TP-403 |
| GAP-09 | Overview/design натякає на різні години працівників | Суперечить SPEC §17.4 | Один clinic-wide schedule; prototype hours — demo text | Clinic + scheduling / TP-206, TP-401 | `in_progress`: ADR-002 і TP-206 clinic-wide schedule done; availability integration лишається TP-401 |
| GAP-10 | Картки показують «Кабінет 1», але prototype не перевіряє room race | Подвійне використання фізичної кімнати | Room catalog, FK/snapshot та DB occupancy constraint | Clinic + scheduling / TP-204, TP-401—402 | `in_progress`: TP-204 catalog/deactivation/history contract done; appointment FK/snapshot і occupancy constraint лишаються TP-401—402 |
| GAP-11 | `design/index.html:308`, `app.js:280` — Suppliers «буде наступним» | Окремий supplier module не вимагається SPEC | Supplier лишається атрибутом receipt/lot; tab прибрати з production nav | Inventory FE/BE / TP-501—502 | `excluded` |
| GAP-12 | Forgot form існує, але admin reset queue відсутня | Запит не має робочого завершення | Enumeration-safe request + admin queue/deep link + temporary password | Accounts FE/BE / TP-202 | `resolved` 2026-07-21 |
| GAP-13 | `#passwordModal` використовується і для own change, і admin reset | Змішуються current-password та privileged reset contracts | Окремі endpoints/forms і force-change flag | Accounts FE/BE + security / TP-202 | `resolved` 2026-07-21 |
| GAP-14 | Hash/query preview та CSS visibility імітують route access | Немає доказу 401/403/404 або IDOR protection | Canonical router guard як UX плюс server policy/selector і negative tests | Accounts + кожен domain + security / TP-201, TP-902 | `cross-cutting` |
| GAP-15 | `design/assets/app.js:320` містить hard-coded analytics datasets | Фільтри змінюють demo numbers, а не ledger/visit projections | Role overview та analytics із контрольованими server read models | Analytics FE/BE + QA / TP-804 | `tracked` |
| GAP-16 | Search/notifications фільтрують статичні DOM rows і локально міняють unread | Можливі stale data, неправильні deep links і role leakage | Scoped server search/notifications, canonical IDs/routes, idempotent read state | Search/notifications + security / TP-801—802 | `tracked` |
| GAP-17 | Photo demo змінює preview/count; clinic logo читається `FileReader`/data URL | Немає private storage, file validation, progress, cleanup або signed access | Upload-intent/finalize/private-read lifecycle; окремий безпечний logo contract | Visits/clinic + security / TP-204, TP-603, TP-902 | `in_progress`: TP-204 private logo contract/storage/validation done; visit photos лишаються TP-603/902 |
| GAP-18 | `app.js:246,262,281,320,330` export buttons показують лише toast | UI обіцяє файл, але export scope/format не погоджено | Прибрати/disable export CTA у production; реалізувати лише новим packet після формату й RBAC рішення | Product + relevant FE / до TP-503, TP-704, TP-803—804 | `excluded` |

## 3. Gate

- Packet не переходить у `done`, якщо пов’язаний `tracked` gap не має implementation evidence або явного accepted scope decision.
- `cross-cutting` gaps перевіряються у Definition of Done кожного PR і повторно у TP-901/TP-902.
- `excluded` demo controls не переносяться у production як активні CTA.
- Після усунення gap owner додає посилання на test/PR і змінює стан на `resolved`; видаляти історичний рядок не можна.
