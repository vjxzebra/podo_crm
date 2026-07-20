# Карта екранів, станів, модалок і рольових доступів Podoria CRM

- Версія: `0.1`
- Статус: базова карта етапу 0
- Функціональне джерело: [`SPECIFICATION.md`](../../SPECIFICATION.md)
- Візуальне джерело: [`design/index.html`](../../design/index.html)
- Пов’язана матриця: [`traceability-matrix.md`](traceability-matrix.md)
- Пов’язана доменна модель: [`domain-model.md`](../architecture/domain-model.md)

## 1. Призначення і правила

Документ визначає цільову інформаційну архітектуру React-застосунку, обов’язкові стани кожної поверхні та доступ трьох фіксованих ролей. Він не переносить демонстраційну логіку прототипу в production-код.

Правила:

- `SPECIFICATION.md` має пріоритет над HTML/CSS/JavaScript прототипу;
- production-роль не перемикається role switcher-ом: вона надходить із серверної сесії;
- приховування елемента в CSS не є авторизацією;
- маршрут, API selector і serializer повинні застосовувати одну access policy;
- чужий object ID не повинен розкривати існування об’єкта;
- ресепшн отримує окрему безпечну patient/visit schema без медичних полів;
- подолог отримує пацієнтів і записи лише у власному relationship scope;
- modal/sheet, відкритий із URL, після закриття повертає до батьківського екрана без втрати його фільтрів і scroll state;
- усі mutation-форми підтримують field validation, server error, submitting, success та unsaved-changes confirmation;
- browser-візуалізація є окремим gate: поточна карта перевірена за DOM-структурою, сценаріями й responsive CSS прототипу.

## 2. Позначення доступу

| Позначка | Значення |
|---|---|
| `full` | Повний доступ у межах функціоналу екрана |
| `all-safe` | Усі дозволені об’єкти, але лише безпечна рольова schema |
| `own` | Лише об’єкти, пов’язані з поточним подологом або власною касовою зміною |
| `limited` | Лише явно перелічені поля або дії |
| `—` | Маршрут, навігація, API та пошук недоступні |

Ролі: `admin` — адмін/власник, `reception` — ресепшн, `podologist` — подолог.

## 3. Цільові маршрути й основні екрани

Hash і query preview-параметри прототипу потрібні лише для демонстрації. Production React Router використовує наведені нижче canonical routes.

| ID | Екран / canonical route | Admin | Reception | Podologist | Основні підповерхні | Обов’язкові стани | Прототип / специфікація |
|---|---|---|---|---|---|---|---|
| AUTH-01 | Вхід `/login` | public | public | public | email, password, show/hide, forgot-password action | idle, submitting, invalid credentials без account enumeration, inactive profile, rate limited, offline, success redirect | `#loginScreen`; §3.1 |
| AUTH-02 | Перший вхід `/first-login` | own | own | own | new password, confirmation, password visibility | forced route, validation, submitting, expired temporary password, success + session rotation | `#firstLoginModal`; §3.2 |
| SCR-01 | Огляд `/app/overview` | full | full | own | role-specific stats, schedule, next appointment, workitems | loading, empty day, partial widget error, stale/retry, success toast | `#overviewView`; §5 |
| SCR-02 | Календар `/app/calendar` | full | full | own | day primary, week secondary, filters, free slots, appointment cards | loading, empty day, no free slots, conflict refresh, filtered empty, permission-safe events | `#calendarView`; §6, AC-02—AC-04 |
| SCR-03 | Пацієнти `/app/patients` | full | all-safe | own | list/search and selected patient shell | loading, empty database, no search results, duplicate-phone warning, forbidden/not-found, pagination | `#patientsView`; §7 |
| SCR-03A | Картка `/app/patients/:patientId/overview` | full | limited | own | identity, contacts, next/last appointment; medical blocks only admin/podologist | loading, redacted reception view, not-found/foreign ID, edit validation, unsaved | `#recordOverview`; §7.4–7.5 |
| SCR-03B | Історія `/app/patients/:patientId/visits` | full | limited | own | reception: appointment/completion facts; medical roles: clinical summary, services, recommendations links | loading, empty history, pagination, redacted fields, detail error | `#recordHistory`; §7.6 |
| SCR-03C | Фото `/app/patients/:patientId/photos` | full | — | own | visit-grouped before/after archive | loading, empty archive, failed private image, carousel, forbidden IDOR | `#recordPhotos`; §7.7 |
| SCR-03D | Рекомендації `/app/patients/:patientId/recommendations` | full | — | own | visit/date/author list, add/edit for authorized medical role | loading, empty, validation, unsaved, save error | prototype placeholder `#recordRecommendations`; §7.8 |
| SCR-04 | Команда `/app/team` | full | — | — | staff list/search/filter, selected profile, role summary | loading, empty, validation, last-admin conflict, inactive state | `#teamView`; §12 |
| SCR-05 | Фінанси `/app/finance/operations` | full | full | — | operations, unpaid visits, current shift | loading, empty, filter empty, no open shift, already paid/refunded, insufficient cash | `#financeView`, `#financeOperationsContent`; §9–10 |
| SCR-05A | Касові зміни `/app/finance/shifts` | full | own | — | period filter, history, selected shift operations | loading, empty, closed/open/discrepancy, foreign shift forbidden | `#cashHistoryContent`; §10.5; reception scope differs from prototype |
| SCR-06 | Склад `/app/inventory/materials` | full | — | — | catalog, filters, low-stock/expiry alerts | loading, empty, filter empty, low/expired/healthy states | `#stockView`, `#stockCatalogPanel`; §11.1–11.3 |
| SCR-06A | Рухи `/app/inventory/movements` | full | — | — | append-only movement journal and filters | loading, empty, filter empty, linked visit/manual/receipt/stocktake rows | `#stockMovementsPanel`; §11.8 |
| SCR-07 | Аналітика `/app/analytics` | full | — | — | period, specialist, service filters; KPI/cards/charts | loading, empty dataset, partial query error, invalid range, refreshed values | `#analyticsView`; §13 |
| SCR-08 | Журнал дій `/app/audit` | full | — | — | search, employee/section/date filters, event details | loading, empty, filter empty, redacted secrets, immutable detail | `#auditView`; §14 |
| SCR-09 | Налаштування `/app/settings/profile` | full | — | — | clinic profile | loading, validation, logo upload progress/error, unsaved, success | `#settingsView`, `#generalSettingsPanel`; §17.1 |
| SCR-09A | Послуги `/app/settings/services` | full | — | — | search, active/inactive list, price/duration/color | loading, empty, validation, deactivate confirm, historical reference retained | `#serviceSettingsPanel`; §17.2 |
| SCR-09B | Робочий час `/app/settings/schedule` | full | — | — | workdays, start/end, multiple breaks | loading, invalid/overlapping/out-of-hours break, unsaved, success | `#scheduleSettingsPanel`; §17.4 |
| SCR-09C | Статуси `/app/settings/statuses` | full | — | — | 8 system statuses, label/color/manual-role policy | loading, validation, protected system status, unsaved, success | `#statusSettingsPanel`; §6.9, §17.3 |

## 4. Детальна рольова матриця

| Поверхня або набір даних | Admin | Reception | Podologist | Обмеження даних / дій |
|---|---|---|---|---|
| Огляд | `full` | `full` | `own` | Кожна роль має окремий read model; подолог не отримує clinic finance або чужий schedule |
| Календар і appointment facts | `full` | `full` | `own` | Подолог може створювати запис лише до себе |
| Контакти пацієнта | `full` | `all-safe` | `own` | Podologist relationship: був або буде запис до поточного подолога |
| Скарги, огляд, клінічні нотатки | `full` | `—` | `own` | Поля відсутні у reception JSON, а не просто hidden |
| Історія записів і факт завершення | `full` | `all-safe` | `own` | Reception schema без clinical summary, photos і recommendations |
| Фото до/після | `full` | `—` | `own` | Private signed access лише після object-scope check |
| Рекомендації | `full` | `—` | `own` | Додавання/редагування лише medical roles у дозволеному scope |
| Оформлення прийому | `full` | `—` | `own` | Подолог лише власний appointment/visit; admin має support access з audit |
| Workitems / справи | `full` | `own` | `own` | Assignee та дозволений patient scope перевіряються сервером |
| Оплати й повернення | `full` | `full` | `—` | Лише завершені visits; повна сума; open-shift rules |
| Внесення й вилучення | `full` | `own` | `—` | Поточна зміна працівника; без patient і payment method |
| Поточна касова зміна | `full` | `own` | `—` | Reception не бачить чужу відкриту зміну |
| Історія касових змін | `full` | `own` | `—` | Prototype admin-only є помилкою щодо §2.2 і §10.5 |
| Склад | `full` | `—` | `—` | Жодних stock quantities у пошуку/сповіщеннях неавторизованих ролей |
| Команда | `full` | `—` | `—` | Self password change не надає доступу до team screen |
| Аналітика | `full` | `—` | `—` | Aggregates також авторизуються, не лише raw records |
| Audit | `full` | `—` | `—` | Secrets/password hashes ніколи не потрапляють у before/after |
| Налаштування | `full` | `—` | `—` | Ролі фіксовані; конфігуруються лише дозволені status transitions |

## 5. Глобальний пошук і сповіщення

### 5.1. Категорії глобального пошуку

| Категорія | Admin | Reception | Podologist | Deep link |
|---|---|---|---|---|
| Пацієнти | усі | усі safe contacts | лише власні | `SCR-03A` |
| Записи | усі | усі | лише власні | `MOD-04` на `SCR-02` |
| Оплати | усі | усі дозволені finance records | — | `MOD-08` на `SCR-05` |
| Матеріали | усі | — | — | `MOD-13` на `SCR-06` |

Search backend спочатку застосовує policy/scope, а потім ранжує й серіалізує результати. Заборонені категорії не повертаються з нульовою кількістю і не розкривають факт збігу.

### 5.2. Сповіщення

| Роль | Дозволені класи подій | Заборонені витоки |
|---|---|---|
| Admin | clinic, inventory, audit, password reset, finance, scheduling | Паролі, секрети, зайві medical details у preview |
| Reception | scheduling, unpaid visit, payment, callback, own cash shift | Clinical notes, photos, inventory quantities, admin audit |
| Podologist | own appointments/patients, patient arrived, own workitems, missing visit photo | Clinic finance, чужі patients/appointments, inventory/audit |

Prototype-орієнтири: `#globalSearchPanel`, `#notificationPanel`. Цільові стани: closed/open, loading, grouped results, no results, all/unread, read/unread, optimistic read with rollback, invalid/forbidden deep link, mobile full screen.

## 6. Реєстр модальних і повноекранних робочих поверхонь

| ID | Поверхня / prototype ID | Відкривається з | Admin | Reception | Podologist | Ключові стани й правила закриття |
|---|---|---|---|---|---|---|
| MOD-01 | Запит відновлення `#forgotPasswordModal` | AUTH-01 | public | public | public | idle, invalid email, submitting, generic success; не підтверджує існування account |
| MOD-02 | Перший пароль `#firstLoginModal` | forced auth flow | own | own | own | не закривається в app shell; mismatch/policy/expired/submitting/success |
| MOD-03 | Новий запис `#modal` | header, calendar slot, patient card, search, visit finish | full | full | own | generic/slot-prefilled/patient-locked, patient search/inline create, validation, conflict, unsaved |
| MOD-04 | Деталі запису `#appointmentDetailsModal` | calendar/search/notification | full | full | own | loading, allowed status actions, reschedule/cancel confirm, foreign ID forbidden |
| MOD-05 | 4-step visit `#visitWorkspaceModal` | own appointment | full | — | own | draft/loading, 4 steps, validation, save, unsaved close, conflict, finishing/idempotency, retry |
| MOD-06 | Фото-відвідування `#photoCarouselModal` | patient photos/history | full | — | own | before/after, loading/private image error, upload progress, delete confirm, keyboard/focus trap |
| MOD-07 | Нова справа `#taskModal` | overview/patient callback | full | own | own | patient prefill/search/empty, important, assignee scope, validation, unsaved, success |
| MOD-08 | Деталі операції `#transactionDetailsModal` | finance/search | full | full | — | loading, payment/refund links, immutable ledger, forbidden/not-found |
| MOD-09 | Касова операція `#cashOperationModal` | finance actions | full | full | — | payment/refund/deposit/withdrawal variants, patient/payment search only where allowed, open-shift/conflict |
| MOD-10 | Закриття зміни `#closeCashShiftModal` | current shift | full | own | — | expected/actual, counted checkbox, discrepancy, required comment, submitting/idempotent success |
| MOD-11 | Деталі зміни `#cashShiftDetailsModal` | shift history/current shift | full | own | — | loading, full operations list, discrepancy, print/export only if scoped |
| MOD-12 | Надходження `#stockReceiptModal` | inventory | full | — | — | multi-line search, totals, validation, duplicate lot decision, confirm, idempotent submit |
| MOD-13 | Матеріал `#materialDetailsModal` | catalog/search/notification | full | — | — | loading, batches/movements/settings tabs, low/expired/empty lot states |
| MOD-14 | Інвентаризація `#inventoryModal` | inventory | full | — | — | draft, system/actual/difference, search, confirm posting, concurrent-change conflict |
| MOD-15 | Ручне списання `#manualWriteoffModal` | material details | full | — | — | available quantity, reason, over-stock validation, confirm, concurrent conflict |
| MOD-16 | Працівник `#employeeModal` | team | full | — | — | create/edit, role preview, temp password, active/inactive, last-admin conflict, unsaved |
| MOD-17 | Пароль `#passwordModal` | own profile or admin employee action | full | own-self | own-self | own change requires current password; admin reset uses separate form contract; no password in audit values |
| MOD-18 | Послуга `#serviceModal` | settings/services | full | — | — | create/edit, code uniqueness, money/duration/color validation, deactivate confirm |
| MOD-19 | Перерва `#breakModal` | settings/schedule | full | — | — | start/end, overlap/out-of-hours validation, delete confirm, unsaved |
| MOD-20 | Статус `#statusConfigModal` | settings/statuses | full | — | — | protected system status, label/color/manual-role permissions, validation, unsaved |

Modal accessibility contract:

- focus переходить на заголовок або перше invalid field;
- focus trap активний до закриття;
- `Escape` закриває тільки безпечну поверхню без незбережених змін;
- backdrop click не втрачає введені дані без confirmation;
- після закриття focus повертається на trigger;
- на телефоні робочі modal стають fullscreen і мають видиму back/close action;
- destructive confirmation не поєднується з основною edit-формою непомітно.

## 7. Панелі, меню та вкладені picker-и

| ID | Поверхня | Ролі | Стани / поведінка |
|---|---|---|---|
| PNL-01 | Глобальний пошук `#globalSearchPanel` | усі, scoped | closed/open, debounced loading, grouped results, empty, keyboard navigation, deep-link denied |
| PNL-02 | Центр сповіщень `#notificationPanel` | усі, scoped | loading, all/unread, empty, mark-one/all, optimistic rollback, deep link |
| PNL-03 | Profile menu `#profileMenu` | усі | change own password, logout; session-expired state не потребує menu |
| PNL-04 | Mobile «Ще» `#mobileMoreMenu` | усі, filtered | role-safe links, profile, search, notifications; focus trap and scrim |
| PICK-01 | Patient picker у MOD-03 | appointment-authorized roles | debounce, results, no results, duplicate warning, inline create, selected/locked |
| PICK-02 | Service picker у MOD-05 | admin/podologist own visit | loading, search by name/code, no results, duplicate increments quantity |
| PICK-03 | Material/lot picker у MOD-05 | admin/podologist own visit | loading, search name/SKU, FEFO recommendation, expired disabled, insufficient stock |
| PICK-04 | Patient/payment picker у MOD-09 | admin/reception | search by allowed identifiers, no results, completed/unpaid/refundable filters |

## 8. Спільний каталог UI-станів

Кожен task packet посилається на потрібні state IDs. Відсутність стану в прототипі не виключає його з реалізації.

| State ID | Стан | Обов’язкова поведінка | Мінімальне покриття |
|---|---|---|---|
| ST-01 | Initial/loading | Skeleton або локальний progress без стрибка layout; mutation control disabled | Усі API-backed screens і modal |
| ST-02 | Empty | Пояснення, безпечна наступна дія, без fake rows | Lists, calendars, histories, notifications |
| ST-03 | Filtered empty | Зберігає фільтри, пропонує очистити їх | Patients, finance, inventory, audit, analytics |
| ST-04 | Field validation | Помилка біля поля; введення не зникає; focus на першій помилці | Усі форми |
| ST-05 | Server error | Correlation ID, retry де безпечно, введення збережене | Усі API-backed surfaces |
| ST-06 | Forbidden | Жодних даних; safe redirect на overview; audit/security signal за потреби | Routes, deep links, object IDs |
| ST-07 | Not found | Не розрізняє неіснуючий і прихований чужий object там, де це захищає scope | Patient, appointment, visit, payment, photo |
| ST-08 | Conflict/stale | `409` пояснює зайнятий slot, змінений stock, closed shift або duplicate mutation; дає refresh/reselect | Scheduling, visit finish, inventory, finance |
| ST-09 | Submitting/idempotent | Primary action disabled, повторний click не дублює mutation, прогрес видимий | Усі critical mutation |
| ST-10 | Success | Короткий toast/confirmation і оновлений authoritative read model | Усі mutation |
| ST-11 | Unsaved changes | Close/back/navigation вимагає confirmation; draft пропонується лише де визначено | Appointment, visit, settings, inventory forms |
| ST-12 | Offline/retry | Не показує false success; read може показати stale marker; mutation retry з тим самим idempotency key | Shell і critical mutation |
| ST-13 | Session expired | Закриває protected content, веде на login, після входу повертає лише до дозволеного route | Увесь app shell |
| ST-14 | Destructive confirm | Називає точний об’єкт і наслідок; окрема confirm action | Cancel, deactivate, refund, stocktake post, delete photo/break |
| ST-15 | Read-only/immutable | Проведені ledger/stock/audit записи не мають edit action | Finance, shifts, movements, audit |
| ST-16 | Partial widget failure | Інші незалежні widgets лишаються доступними; помилка локалізована | Overview, analytics |

## 9. Feature-specific state map

| Feature | Додаткові стани, які не можна загубити |
|---|---|
| Auth | wrong credentials, inactive user, forced first login, reset request generic success, password mismatch/policy, rate limit |
| Calendar | day/week, all/own specialist, break, free slot, busy slot, parallel specialists, past, cancelled/no-show, slot became busy |
| Patient | no patients, live search empty, possible duplicate phone, selected record, reception redaction, foreign patient ID |
| Visit | draft/saved/dirty, steps 1–4, complaints/no-complaints, duplicate service quantity, insufficient/expired lot, before/after upload, finish rollback/retry |
| Finance | no open shift, unpaid/paid/refunded, full amount read-only, cash/card/transfer, insufficient cash, discrepancy, closed shift |
| Inventory | healthy/low/out/expired, FEFO, receipt draft/posted, stocktake draft/posted, concurrent balance conflict, append-only movement |
| Search | short/empty query, loading, grouped results, no results, category removed by role, forbidden stale deep link |
| Notifications | unread/read, zero count, all/unread filter, mark read rollback, role-safe deep link |

## 10. Responsive map

| Surface | Desktop | Tablet | Phone |
|---|---|---|---|
| Shell | Persistent sidebar + topbar | Compact icon rail + topbar | Bottom nav: overview, calendar, new appointment, patients, more |
| Calendar | Multi-specialist columns, day/week | Podologist one column; other roles compact/horizontal layout | Podologist one column; other roles horizontal specialist scroll |
| Patient list/card | Directory + card side-by-side | Compact directory/card split or drill-in | List → full-screen card; no horizontal table dependence |
| Visit workspace | Fullscreen work area with context sidebar | Full available area, compact context | One-column fullscreen steps, sticky primary action, thumb-reachable controls |
| Data tables | Full columns | Priority columns + details drawer | Cards/rows with drill-in; horizontal scroll only as last resort |
| Modal | Centered, bounded height, focus trap | Large dialog/full available area | Fullscreen sheet/page with explicit back/close |
| Search/notifications | Anchored panel | Wide overlay | Fullscreen |
| Forms | Multi-column where readable | 1–2 columns | One column, keyboard-safe, minimum touch target 44px |

Prototype preview references retained only for visual QA:

- `preview=tablet-calendar`, `tablet-patient`, `tablet-visit`;
- `preview=mobile-calendar`, `mobile-patient`, `mobile-visit`, `mobile-more`, `mobile-search`;
- `preview=login`, `first-login`, `global-search`, `notifications`;
- feature previews listed in `design/assets/app.js` for visit, finance, inventory, team, audit and settings modal states.

## 11. Виявлені розбіжності та рішення карти

| ID | Розбіжність прототипу | Цільове рішення |
|---|---|---|
| GAP-01 | Recommendations — placeholder | Реалізувати повний `SCR-03D` за §7.8 |
| GAP-02 | Cash history tab позначено admin-only | Reception отримує `SCR-05A` лише для власних shifts; admin — усі |
| GAP-03 | Medical fields reception приховуються CSS, але існують у DOM | Окремий server serializer/read model без medical keys |
| GAP-04 | Role switcher змінює роль у браузері | У production роль тільки із session; switcher лишається dev/storybook tool поза production build |
| GAP-05 | Demo mutations змінюють DOM без API і транзакцій | Усі mutation проходять service layer, DB constraints, audit та server response |
| GAP-06 | Loading, API error, conflict, offline і unsaved states майже не представлені | ST-01—ST-16 обов’язкові в task packets і component tests |
| GAP-07 | Settings profile у дизайні не гарантує всі phone/email/address поля | `SCR-09` реалізує повний набір §17.1 |
| GAP-08 | Кількість/набір статусів у prototype може відрізнятися | Джерело правди — 8 system statuses §6.9; delete заборонено |
| GAP-09 | Текст прототипу натякає на індивідуальні графіки | MVP має лише загальний clinic schedule за §17.4; очікує ADR-002 |
| GAP-10 | Rooms показані як повноцінний ресурс, але правило конфлікту не погоджене | UI зберігає room label; booking constraint залежить від ADR-001 |
| GAP-11 | Suppliers tab є placeholder, окремий supplier module не вимагається | У MVP supplier — атрибут receipt/lot; окремий screen виключити без нового scope |
| GAP-12 | Запит на відновлення є на login, але admin queue не показана | Додати admin work queue/deep link у team/security task packet |
| GAP-13 | Prototype password modal змішує own change та admin reset | Розділити API/forms: own change з current password; admin temporary password з force-change flag |
| GAP-14 | Prototype не є доказом route security або IDOR protection | Route guard лише UX; API policy/selector та negative tests є обов’язковими |

## 12. Трасування до критеріїв готовності

| Група поверхонь | Acceptance criteria |
|---|---|
| Role-safe routes, tabs, search, notifications | AC-01, AC-22 |
| Calendar, appointment modal/details | AC-02—AC-07 |
| Visit workspace, pickers, photos, finish | AC-08—AC-12, AC-18 |
| Finance operations and shifts | AC-13—AC-17 |
| Inventory screens and modal | AC-19 |
| Audit screen/details | AC-20 |
| Auth, profile, team password flows | AC-21 |
| Responsive variants of every user-visible surface | AC-23 |

## 13. Gate для завершення UI-карти

Карта вважається реалізованою у feature task packet лише коли:

1. canonical route і parent/overlay relationship зафіксовані;
2. дозволені ролі та data scope мають positive і negative API tests;
3. потрібні ST-state IDs включені в acceptance criteria;
4. reception serializer не містить medical keys;
5. podologist selector не повертає чужі patients/appointments;
6. modal має focus trap, focus return та unsaved guard;
7. desktop/tablet/phone layout перевірений Playwright-проєктами;
8. deep links із search/notifications повторно перевіряють authorization;
9. prototype-only розбіжності не перенесені без ADR або нового scope.
