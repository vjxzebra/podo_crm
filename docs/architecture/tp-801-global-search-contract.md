# TP-801 — рольовий глобальний пошук і canonical deep links

Статус: `frozen` 2026-07-22.

Джерела: `SPECIFICATION.md` §2.4, §16; AC-01, AC-22; `screen-state-access-map.md` §5.1;
GAP-16; TP-301, TP-403, TP-503 і TP-702.

## 1. Межа пакета

TP-801 додає server-side глобальний пошук пацієнтів, записів, оплат і матеріалів,
role-safe overlay на desktop/tablet/mobile та відновлювані після refresh deep links.
Backend є єдиним джерелом scope: frontend не отримує заборонені групи, їх counts або
факти існування збігів.

Не входять: Elasticsearch, повнотекстовий окремий сервіс, повні search-result сторінки,
сповіщення TP-802, audit UI TP-803 і аналітика TP-804.

## 2. Search API

`GET /api/v1/search?q=&types=` потребує authenticated active user.

### 2.1. Query

- `q` обов’язковий; server застосовує Unicode NFKC, trim, collapse whitespace і
  `casefold`; телефон паралельно нормалізується до цифр;
- довжина нормалізованого `q` — від 2 до 100 символів, інакше стандартний `422`
  error envelope;
- `types` необов’язковий comma-separated список із
  `patients,appointments,payments,materials`;
- без `types` шукаються всі дозволені ролі категорії; дублікати дедуплікуються;
- порожній або невідомий token дає `422`; валідна, але заборонена ролі категорія
  мовчки відкидається без `403`, zero-group або count;
- якщо після role intersection категорій немає, відповідь — `200` із порожніми
  `groups` і `returned_count: 0`.

### 2.2. Scope до пошуку

| Категорія | Admin | Reception | Podologist |
|---|---|---|---|
| `patients` | усі safe patient rows | усі safe patient rows | лише `patients_visible_to(actor)` |
| `appointments` | усі | усі | лише `specialist = actor` |
| `payments` | усі Receivable rows | усі Receivable rows | недоступно |
| `materials` | усі material cards | недоступно | недоступно |

Scope queryset будується до match, rank, `has_more`, limit і serialization. Search не
серіалізує medical/visit-photo data, complaints, clinical notes, cash-shift totals або
дані інших категорій.

### 2.3. Response

```json
{
  "query": "наталія",
  "groups": [
    {
      "type": "patients",
      "has_more": false,
      "items": [
        {
          "type": "patient",
          "id": "00000000-0000-0000-0000-000000000000",
          "title": "Наталія Коваль",
          "subtitle": "+380 67 234 56 78",
          "meta": "P-0123456789AB",
          "deep_link": "/patients/00000000-0000-0000-0000-000000000000/overview"
        }
      ]
    }
  ],
  "returned_count": 1
}
```

Групи мають канонічний порядок `patients → appointments → payments → materials`.
Заборонені й порожні групи фізично відсутні. На категорію повертається максимум 5
items; queryset читає 6 дозволених збігів лише для обчислення `has_more`.
`returned_count` — сума фактично серіалізованих items, максимум 20.

Кожен item має мінімальну спільну safe projection:

```text
type: patient | appointment | payment | material
id: UUID
title: string
subtitle: string
meta: string
deep_link: same-origin root-relative path
```

Наповнення:

- patient: display name; safe phone; public patient number;
- appointment: patient + clinic date/time; service; public appointment number,
  specialist і status;
- payment: patient; server-formatted amount + Receivable status; payment ledger number
  або visit public number; лише Receivable category, без окремих refund/deposit/withdrawal;
- material: name; SKU + category; admin-safe stock/status summary.

## 3. Match, ranking та indexes

Пошук підтримує:

- patients — first/last/full name, phone digits, patient public number;
- appointments — appointment number, patient name/phone/number, service name/code;
- payments — patient snapshot/current safe identifiers, visit/payment number,
  service snapshot/code;
- materials — name і SKU.

Rank усередині scoped queryset: exact public number/code/phone → identifier prefix →
name prefix → substring/trigram similarity. Tie-break є стабільним і не залежить від
заборонених rows. Search використовує PostgreSQL `pg_trgm`, нормалізований phone/SKU та
targeted GIN trigram indexes для patient identity, appointment identifiers/snapshots,
payment snapshots/ledger number і material name/SKU. Query-plan evidence виконується на
PostgreSQL; для малих fixtures дозволено `SET LOCAL enable_seqscan=off`, після чого JSON
EXPLAIN має послатися на TP-801 index.

## 4. Canonical deep links

Backend повертає лише такі same-origin links:

| Item | Link | Scoped resolver |
|---|---|---|
| patient | `/patients/{id}/overview` | `GET /api/v1/patients/{id}` |
| appointment | `/calendar?appointment={id}` | `GET /api/v1/appointments/{id}` |
| payment | `/finance?operation=PAYMENT:{receivable_id}` | `GET /api/v1/finance/operations/PAYMENT/{id}` |
| material | `/inventory?material={id}` | `GET /api/v1/inventory/materials/{id}` |

Finance exact resolver у TP-801 гарантує `PAYMENT`; unsupported type, stale UUID і
неавторизований UUID повертають safe `404`. Інші destination APIs уже мають role scope.
Destination page читає query param і повторно робить exact scoped GET; вона не довіряє
search payload та не шукає item у поточній paginated list. Після закриття detail параметр
видаляється через replace navigation. Заборонений route додатково блокується session
route guard.

Root routes є канонічними для поточного React router. Перенесення всіх URL під `/app`
не входить у TP-801.

Quick-create links:

- `/patients?compose=patient`;
- `/calendar?compose=appointment`.

Вони показуються лише коли session `route_ids` містить відповідний route; mutation API
повторно застосовує власний scope.

## 5. Overlay contract

Пошук відкривається desktop trigger, mobile «Ще» або `Ctrl/Cmd+K`. UI має стани idle,
short query, 250 ms debounce, loading, grouped success, empty, error/retry. Він скасовує
або ігнорує stale requests, рендерить лише server groups, перевіряє root-relative
`deep_link`, підтримує ArrowUp/ArrowDown/Home/End/Enter/Escape, focus trap і повернення
focus. На mobile overlay fullscreen; body scroll заблокований лише поки dialog відкритий.

## 6. Обов’язковий доказ

- role fixtures із точними забороненими збігами для всіх трьох ролей;
- requested forbidden `types`, cross-role IDOR і відсутність leaked groups/counts;
- normalization, ranking, stable order, 5+`has_more`, indexes та query plan;
- exact deep-link refresh/stale/404 для чотирьох destination types;
- component tests для shortcut/debounce/stale/loading/grouped/empty/error/keyboard/focus;
- axe та authenticated desktop/tablet/mobile browser gate без page overflow і console
  errors;
- OpenAPI JSON snapshot, generated TypeScript types, migration cycle й canonical backend
  та frontend quality gates.
