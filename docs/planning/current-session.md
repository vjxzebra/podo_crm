# Поточний checkpoint розробки

Дата: 2026-07-21

## Зафіксований стан

- TP-201—TP-205 і TP-207 завершені.
- Реалізовані session auth/RBAC, password lifecycle, команда працівників, append-only audit, профіль клініки, приватний логотип, кабінети та каталог послуг.
- OpenAPI snapshot і TypeScript API schema оновлені разом із backend/frontend реалізацією.
- Browser evidence для TP-203, TP-204 і TP-205 збережені в `docs/evidence/`.
- Кореневий `AGENTS.md` вимагає окремо діагностувати й відновлювати несправні локальні компоненти замість повторення того самого невдалого виклику.

## Локальне середовище

- Docker Compose stack відновлений і readiness endpoint повертає `200`.
- Завислий orphan-контейнер `podoria-crm-backend-stuck` видалений; робочий контейнер `podoria-crm-backend-1` healthy.
- Вбудований браузер перевірений на `http://127.0.0.1:8088/settings`.
- Локальні credentials тестового адміністратора зберігаються лише в проігнорованому `.env.local`; `README.md` містить команду відтворення без відкритого пароля, а `.env.example` — безпечні placeholders.
- Повний `scripts/run-tests.ps1` пройшов: 80 backend tests, 30 frontend tests, lint, typecheck, contracts check, OpenAPI snapshot і production build.

Browser adapter має точкове локальне виправлення у встановленому plugin cache для сумісності із захищеним `process` рантайму та вимкнення несправної ambient telemetry у browser runtime. Це виправлення лежить поза репозиторієм і може бути перезаписане під час оновлення плагіна; у такому разі потрібно окремо відновити компонент за правилом з `AGENTS.md`.

## Наступний пакет

Наступна запланована робота — TP-206: системні статуси та clinic-wide work schedule.
