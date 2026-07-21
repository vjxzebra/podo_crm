# TP-301 patient directory evidence

Перевірено 2026-07-21 через production build та authenticated in-app browser на локальному Compose stack. Browser виконав реальні `POST /patients`, live search, empty state, duplicate-phone warning, non-blocking duplicate create й unsaved close guard. Усі створені записи є вигаданими demo-даними.

| Critical path | Viewport | Результат | Evidence |
|---|---:|---|---|
| Patient directory | 1440×900 | Два persisted patients, public numbers, safe contacts, unassigned podologist and no-appointment projections, admin scope | [patient-directory-1440x900.png](patient-directory-1440x900.png) |
| Responsive cards | 768×1024 | Compact rail, two-column patient cards, `scrollWidth = innerWidth`, no horizontal overflow | [patient-directory-768x1024.png](patient-directory-768x1024.png) |
| Mobile directory | 390×844 | One-column cards, mobile bottom navigation, search/create controls and no page overflow | [patient-directory-390x844.png](patient-directory-390x844.png) |
| Duplicate + unsaved guard | 390×844 | Existing same-phone matches visible, create stays available, close requires explicit discard | [patient-duplicate-unsaved-390x844.png](patient-duplicate-unsaved-390x844.png) |

Автоматизовані докази:

- backend: 110 tests загалом; TP-301 додає 17 cases для local/international phone normalization, invalid phone/date/name fields, indexed non-unique normalized phone, unique public number, full-name/phone/public-number search, stable cursor pages, admin/reception/podologist scopes, foreign duplicate non-disclosure, own assignment, safe reception keys, authentication та same-transaction audit;
- frontend: 40 tests, з них 8 axe-core routes; TP-301 покриває list/scope, live empty search, inline create, duplicate warning, unsaved guard, cursor append і `/patients` accessibility;
- OpenAPI snapshot та generated TypeScript client містять role-scoped `GET /patients?search=&cursor=` і audited `POST /patients` із immediately reusable `patient` reference та safe `possible_duplicates`;
- full backend gate, fresh frontend container gate і production web image build пройшли; Compose readiness повертає `200`.

Patient detail/edit, medical profile, history, photos and appointment-derived podologist relationships не входять у TP-301 та переходять у TP-302/TP-401+.
