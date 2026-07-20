# TP-103 responsive shell evidence

Перевірено 2026-07-20 у Microsoft Edge `150.0.4078.83`. Screenshot harness задав точний CSS viewport, дочекався `networkidle` і перевірив, що `document.documentElement.scrollWidth <= window.innerWidth`.

| Surface | Viewport | Navigation contract | Evidence |
|---|---:|---|---|
| Desktop | 1440×900 | Persistent 248 px sidebar, topbar, multi-column overview | [desktop-1440x900.png](desktop-1440x900.png) |
| Tablet | 768×1024 | 82 px icon rail, full feature set, stacked dashboard panels | [tablet-768x1024.png](tablet-768x1024.png) |
| Phone | 390×844 | Mobile topbar, thumb-safe bottom navigation, single-column content | [mobile-390x844.png](mobile-390x844.png) |

Automated evidence: 9 component/route/auth-boundary tests and 5 axe-core checks cover overview, loading, empty, error, 403 and 404 shells. `color-contrast` is excluded only in JSDOM because axe-core documents it as unsupported there; visual contrast remains part of the screenshots/manual review.
