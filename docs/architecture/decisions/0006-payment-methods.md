# ADR-006: Способи оплати MVP

- Статус: `Accepted`
- Дата створення: 2026-07-20
- Дата погодження: 2026-07-20
- Власник рішення: Product owner + finance owner
- Цільова дата рішення: 2026-07-22
- Залежні етапи: 7, 8, 9

## Контекст

Специфікація вимагає вибір і фільтр способу оплати, явно згадує готівку й картку, але не задає закритий enum. План пропонує готівку, картку та переказ. Часткові оплати не підтримуються, тому один payment має один method.

## Рішення

- Закритий перелік MVP: `CASH`, `CARD`, `TRANSFER`.
- Один payment повністю закриває один receivable та має рівно один method; split tender відсутній.
- `CASH` впливає на очікувану фізичну готівку поточної касової зміни.
- `CARD` і `TRANSFER` входять у виторг і method totals, але не змінюють physical cash.
- Refund успадковує method початкового payment; користувач не обирає інший method.
- `DEPOSIT` і `WITHDRAWAL` завжди є cash adjustments і не мають `payment_method` field.
- Зміна переліку потребує нового ADR, enum migration, OpenAPI/client update та перегляду аналітики.

## Наслідки

- API та DB використовують стабільні codes; українські labels належать presentation layer.
- Cash shift detail і analytics показують окремі totals `cash`, `card`, `transfer`.
- Зовнішня платіжна інтеграція, acquiring status і transaction provider ID не входять до MVP.
- Для `CARD`/`TRANSFER` система фіксує ручне підтвердження факту оплати, а не проводить кошти.

## Відхилені альтернативи

- Лише готівка/картка: не покриває запропонований у плані банківський переказ.
- Довільний текстовий спосіб: ламає стабільні фільтри, звіти та constraints.
- Split tender: суперечить простій моделі одного повного payment у MVP.

## Критерії перевірки

- OpenAPI відхиляє невідомий method і не дозволяє method для cash adjustment.
- Expected cash змінюється лише для `CASH` payment/refund і cash adjustments.
- Refund method завжди дорівнює method початкової payment.
