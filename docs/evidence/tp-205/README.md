# TP-205 service catalog evidence

Перевірено 2026-07-21 через production build і Microsoft Edge `150.0.4078.83` з точними CSS viewport. Вбудований browser connector зупинився на повторюваному bootstrap conflict середовища, тому critical path виконано відтворюваним fallback-скриптом `frontend/scripts/tp205-browser-check.mjs`.

| Critical path | Viewport | Результат | Evidence |
|---|---:|---|---|
| Admin service catalog/search/status | 1440×900 | П’ять persisted service rows, minor-unit prices, duration, calendar colors, active/inactive state, search і edit controls | [service-catalog-1440x900.png](service-catalog-1440x900.png) |
| Create form і palette | 768×1024 | Повні code/name/duration/price fields, 8 keyboard-accessible colors, active control і no-delete/history пояснення; tablet tabs не створюють horizontal overflow | [service-create-palette-768x1024.png](service-create-palette-768x1024.png) |
| Responsive service cards | 390×844 | Table переходить у touch-friendly cards із color/code/duration/price/status/edit без horizontal overflow | [service-cards-390x844.png](service-cards-390x844.png) |

Автоматизовані докази:

- backend: 80 tests загалом; TP-205 додає 12 tests для search/filter/detail, normalization, zero price, validation, case-insensitive code conflict, duration/price DB constraints, optimistic conflict, deactivate/reactivate/no-delete, RBAC, active picker projection та audit;
- frontend: 30 tests, з них 7 axe-core routes; TP-205 покриває search/empty/reset, create, palette, гривня→minor conversion і retained server conflict;
- OpenAPI snapshot і generated TypeScript client містять `GET/POST /services` та `GET/PATCH /services/{id}` з integer `price_minor` і versioned admin mutations;
- live Edge check: `{"desktopCatalog":"ok","tabletPalette":"ok","mobileCards":"ok","receptionPickerBoundary":"ok"}`.

Protocol templates, categories, specialist assignments і visit line quantities не входять у TP-205. Неактивна послуга відсутня в picker projection для нових записів, але row не видаляється; майбутні visit lines зберігатимуть code/name/price snapshot у TP-602.
