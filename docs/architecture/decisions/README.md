# Реєстр архітектурних рішень Podoria CRM

Цей каталог фіксує рішення, які уточнюють `SPECIFICATION.md` і мають бути прийняті до створення залежних migrations та API-контрактів.

## Статуси

- `Proposed` — рішення підготовлене, але ще потребує погодження власником;
- `Accepted` — рішення є обов’язковим контрактом;
- `Superseded` — рішення замінене новим ADR;
- `Rejected` — варіант відхилено і не реалізується.

Поки ADR має статус `Proposed`, його default можна використовувати для документації, прототипування та task packets, але не для незворотних migrations.

## Реєстр

| ADR | Рішення | Статус | Власник рішення | Цільова дата |
|---|---|---|---|---|
| [ADR-001](0001-rooms-and-occupancy.md) | Кімнати та контроль їх зайнятості | `Proposed` | Product owner + tech lead | 2026-07-22 |
| [ADR-002](0002-clinic-wide-schedule.md) | Єдиний графік кабінету | `Proposed` | Product owner | 2026-07-22 |
| [ADR-003](0003-full-refunds-only.md) | Лише повні повернення | `Proposed` | Product owner + finance owner | 2026-07-22 |
| [ADR-004](0004-private-visit-photos.md) | Формати, ліміти та зберігання фото | `Proposed` | Product owner + security owner | 2026-07-22 |
| [ADR-005](0005-backup-and-restore-policy.md) | Backup, RPO/RTO та restore drills | `Proposed` | Tech lead / operations owner | 2026-07-22 |
| [ADR-006](0006-payment-methods.md) | Способи оплати MVP | `Proposed` | Product owner + finance owner | 2026-07-22 |

## Правило погодження

Під час погодження власник рішення:

1. підтверджує запропонований варіант або вносить конкретну заміну;
2. змінює статус ADR на `Accepted` і додає дату погодження;
3. оновлює залежні ERD, traceability matrix та task packets;
4. лише після цього дозволяє залежні migrations і production-конфігурацію.
