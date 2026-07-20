# ADR-005: Backup і відновлення

- Статус: `Proposed`
- Дата створення: 2026-07-20
- Власник рішення: Tech lead / operations owner
- Цільова дата рішення: 2026-07-22
- Залежні етапи: 1, 9

## Контекст

PostgreSQL і MinIO містять взаємопов’язані business та medical records. Зберігання backup на тому самому production host не захищає від втрати хоста або помилки оператора. Redis і Celery queues не є джерелом business truth.

## Запропоноване рішення

- Щодня створюється зашифрований PostgreSQL backup і versioned backup приватного MinIO bucket у сховищі поза production host.
- Цільовий `RPO ≤ 24 години`, `RTO ≤ 4 години` для відновлення сервісу на підготовленій інфраструктурі.
- Retention: 30 щоденних і 12 щомісячних recovery points.
- Backup credentials відокремлені від application credentials; production application role не може видаляти backup.
- Шифрування діє під час передачі та зберігання; доступ і спроби restore журналюються операційно.
- Redis, derived previews, build artifacts і Celery queues окремо не backup-яться; вони відтворюються з PostgreSQL/MinIO або deployment artifacts.
- Automated job перевіряє завершення, розмір і checksum кожного backup; failure створює alert.
- Не рідше одного разу на місяць виконується restore drill в ізольованому середовищі з перевіркою DB migrations, вибіркових private photos і referential integrity.

## Наслідки

- `infra/` має містити backup/restore runbook, конфігурацію retention та monitoring check.
- Production readiness gate блокується без успішного restore drill.
- Видалені primary data можуть залишатися у recovery points до завершення retention window; це треба враховувати в процедурі видалення даних.
- Конкретний cloud/provider не фіксується цим ADR і може бути вибраний deployment packet-ом за умови off-host isolation.

## Відхилені альтернативи

- Backup лише на production volume: не переживає втрату або компрометацію хоста.
- Backup без restore drill: не дає доказу відновлюваності.
- Backup Redis/queues як джерела truth: відновлює нестабільний transient state.

## Критерії перевірки

- Моніторинг сигналізує про пропущений або пошкоджений recovery point.
- Документований restore вкладається в RTO на контрольному dataset.
- Відновлена DB не містить photo references без доступного primary object або зафіксованого tombstone.
