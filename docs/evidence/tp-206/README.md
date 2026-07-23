# TP-206 system status and clinic schedule evidence

Перевірено 2026-07-21 через production build і Microsoft Edge `150.0.4078.83` з точними CSS viewport. Вбудований browser успішно перевірив authenticated DOM, обидві вкладки, вісім status rows, editor/unsaved state та mobile bounding boxes. Після кількох viewport-перемикань його PNG compositor повертав stale/cropped tiles, тому відтворювані фінальні screenshots створені fallback-скриптом `frontend/scripts/tp206-browser-check.mjs`; невалідний проміжний PNG видалено.

| Critical path | Viewport | Результат | Evidence |
|---|---:|---|---|
| Eight protected status configs | 1440×900 | Рівно 8 persisted system codes у workflow order; label/color/manual-role summary; edit controls; no create/delete | [status-configs-1440x900.png](status-configs-1440x900.png) |
| Protected editor + unsaved state | 768×1024 | System code показаний read-only, три role flags доступні, color/label редагуються, незбережені зміни явні | [status-editor-unsaved-768x1024.png](status-editor-unsaved-768x1024.png) |
| Clinic-wide weekly schedule | 1440×900 | 7 days, 5 working weekdays, multiple-break controls, `Europe/Kyiv`, working/closed states | [clinic-schedule-1440x900.png](clinic-schedule-1440x900.png) |
| Responsive schedule card | 390×844 | Одноколонкові day cards, усі time/break controls у viewport, mobile navigation і horizontally scrollable settings tabs без page overflow | [clinic-schedule-390x844.png](clinic-schedule-390x844.png) |

Автоматизовані докази:

- backend: 93 tests загалом; TP-206 додає 13 cases для exact seed registry, status code/update/delete protection у model/queryset/PostgreSQL trigger, color/role/version API, seven-day schedule, atomic update/audit, out-of-hours/reversed/overlapping breaks, DB time constraints та RBAC;
- frontend: 33 tests, з них 7 axe-core routes; TP-206 покриває 8-row editor, immutable code absence, manual-role flags, unsaved state, typed seven-day PUT та retained server validation;
- OpenAPI snapshot і generated TypeScript client містять admin-only `GET /appointment-status-configs`, `PATCH /appointment-status-configs/{code}` та `GET/PUT /clinic-workdays`;
- live Edge check: `{"desktopStatuses":"ok","desktopSchedule":"ok","tabletStatusEditor":"ok","mobileSchedule":"ok"}`;
- full backend gate, fresh frontend container gate і production web image build пройшли після окремого відновлення одноразового frontend-test process crash; пізніший Docker Desktop exit-event hang усунуто точковим restart і підтверджено новим одноразовим container typecheck.

Holidays, vacations, one-off exceptions, booking horizon, timezone/step configuration та specialist-specific schedules не входять у TP-206. Availability і appointment transition enforcement використовуватимуть ці довідники у TP-401/TP-403.
