# ADR-004: Приватні фото відвідувань

- Статус: `Accepted`
- Дата створення: 2026-07-20
- Дата погодження: 2026-07-20
- Власник рішення: Product owner + security owner
- Цільова дата рішення: 2026-07-22
- Залежні етапи: 1, 3, 6, 9

## Контекст

Фото «до» і «після» є медичними даними конкретного visit. Специфікація вимагає окремі блоки, preview та видалення до завершення, але не задає формат, розмір, кількість, доступ, orphan cleanup і retention після завершення.

## Рішення

- Приймаються `JPEG`, `PNG` і `WebP`, перевірені за magic bytes та успішним декодуванням, а не лише за extension/MIME від клієнта.
- Максимум 10 МБ на файл, 10 фото `BEFORE` і 10 фото `AFTER` на visit.
- Об’єкти зберігаються лише у private MinIO bucket; публічні URL заборонені.
- Читання проходить object-level authorization і видає signed URL не довше ніж на 5 хвилин.
- Canonical image після upload видаляє EXIF/GPS metadata; preview генерується асинхронно після commit.
- Upload intent діє 60 хвилин; неприкріплені об’єкти видаляються cleanup job після 24 годин.
- Фото draft-visit можна видалити до finish. Після `COMPLETED` звичайне редагування або видалення заборонене.
- Completed photos зберігаються разом із patient record без автоматичного expiry у MVP. Виняткове видалення можливе лише окремою admin/support процедурою з підставою, audit event і перевіркою чинних вимог до даних.
- Backup retention для фото визначає ADR-005; видалений primary object зникає з backup лише після завершення backup retention window.

## Наслідки

- Потрібні upload-intent, finalize, authorized-read і draft-delete contracts.
- Reception serializers та global search не повертають photo metadata або URLs.
- У `finish_visit` усі прикріплені фото мають бути успішно finalized; processing failure лишає visit у draft.
- HEIC/HEIF не підтримується в MVP і має отримати зрозумілу validation error.

## Відхилені альтернативи

- Public bucket: створює неконтрольований витік медичних даних.
- Зберігання base64 у PostgreSQL: погіршує backup, delivery та масштабування.
- Автоматичне видалення completed photos за коротким TTL: руйнує історію відвідування без погодженої legal/business підстави.

## Критерії перевірки

- Чужий або reception user не отримує object existence, metadata чи signed URL.
- Файл із підробленим MIME, понад 10 МБ або 11-те фото одного kind відхиляється.
- Cleanup не видаляє finalized photo; draft delete не працює після completion.
