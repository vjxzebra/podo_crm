import { useState } from "react";
import { Link } from "react-router";

import { apiClient } from "../api/client";
import {
  errorFixture,
  successFixture,
  type ContractSuccess,
  type ErrorEnvelope,
} from "../contractFixtures";
import { Icon } from "./Icon";
import type { AppRouteDefinition } from "./routes";

const statePreviews = [
  { path: "/previews/loading", label: "Loading" },
  { path: "/previews/empty", label: "Empty" },
  { path: "/previews/error", label: "Error" },
  { path: "/previews/forbidden", label: "403" },
  { path: "/preview-that-does-not-exist", label: "404" },
] as const;

export function StatePreviewLinks() {
  return (
    <nav className="state-preview-links" aria-label="Прев’ю системних станів">
      <span>Стани:</span>
      {statePreviews.map((preview) => (
        <Link key={preview.path} to={preview.path}>
          {preview.label}
        </Link>
      ))}
    </nav>
  );
}

const overviewStats = [
  { label: "Записи сьогодні", value: "12", note: "+2 до вчора", tone: "sage", icon: "calendar" },
  { label: "Пацієнти", value: "8", note: "3 нові", tone: "sand", icon: "patients" },
  { label: "Робочий час", value: "7 год", note: "до 18:30", tone: "lilac", icon: "analytics" },
  { label: "Потребує уваги", value: "2", note: "перевірити", tone: "coral", icon: "bell" },
] as const;

export function OverviewPage() {
  return (
    <>
      <header className="page-heading overview-heading">
        <div>
          <p className="eyebrow">Понеділок, 20 липня · UI preview</p>
          <h1>Добрий день</h1>
          <p>Операційний огляд майбутньої серверної сесії без реальних даних.</p>
        </div>
        <div className="date-switcher" aria-label="Навігація за датою">
          <button type="button" aria-label="Попередній день">
            <Icon name="arrow-left" />
          </button>
          <span>Сьогодні</span>
          <button type="button" aria-label="Наступний день">
            <Icon name="chevron" />
          </button>
        </div>
      </header>

      <StatePreviewLinks />

      <section className="stats-grid" aria-label="Демонстраційні показники">
        {overviewStats.map((stat) => (
          <article className="stat-card" key={stat.label}>
            <span className={`stat-card__icon stat-card__icon--${stat.tone}`}>
              <Icon name={stat.icon} />
            </span>
            <span className="stat-card__copy">
              <small>{stat.label}</small>
              <strong>{stat.value}</strong>
              <span>{stat.note}</span>
            </span>
          </article>
        ))}
      </section>

      <div className="dashboard-grid">
        <section className="panel schedule-panel" aria-labelledby="schedule-heading">
          <header className="panel__heading">
            <div>
              <p className="eyebrow">Розклад</p>
              <h2 id="schedule-heading">Сьогоднішні записи</h2>
              <p>Демонстраційний вміст із прототипу</p>
            </div>
            <Link className="text-link" to="/calendar">
              Увесь календар <Icon name="chevron" />
            </Link>
          </header>
          <div className="timeline">
            <article className="timeline-item timeline-item--complete">
              <time>09:30</time>
              <span className="timeline-item__rail" aria-hidden="true" />
              <div className="appointment-card">
                <span className="avatar avatar--sage" aria-hidden="true">
                  НК
                </span>
                <span>
                  <strong>Наталія Коваль</strong>
                  <small>Первинна консультація · 45 хв</small>
                </span>
                <span className="status-pill">Завершено</span>
              </div>
            </article>
            <article className="timeline-item">
              <time>11:00</time>
              <span className="timeline-item__rail" aria-hidden="true" />
              <div className="appointment-card appointment-card--active">
                <span className="avatar avatar--lilac" aria-hidden="true">
                  ІС
                </span>
                <span>
                  <strong>Ірина Савчук</strong>
                  <small>Медичний педикюр · 60 хв</small>
                </span>
                <span className="status-pill status-pill--sand">Очікує</span>
              </div>
            </article>
            <article className="timeline-item">
              <time>13:30</time>
              <span className="timeline-item__rail" aria-hidden="true" />
              <div className="appointment-card appointment-card--break">
                <span className="appointment-card__break-icon" aria-hidden="true">
                  ☕
                </span>
                <span>
                  <strong>Перерва</strong>
                  <small>30 хв</small>
                </span>
              </div>
            </article>
          </div>
        </section>

        <div className="dashboard-side">
          <section className="panel next-patient" aria-labelledby="next-patient-heading">
            <header className="panel__heading">
              <div>
                <p className="eyebrow"><span className="live-dot" /> Наступний пацієнт</p>
                <h2 id="next-patient-heading">Через 24 хв</h2>
              </div>
              <span className="status-pill">Підтверджено</span>
            </header>
            <div className="patient-hero">
              <span className="avatar avatar--large avatar--lilac" aria-hidden="true">
                МБ
              </span>
              <span>
                <strong>Марія Бондар</strong>
                <small>Повторний візит · прототип</small>
              </span>
            </div>
            <dl className="patient-facts">
              <div><dt>Час</dt><dd>12:00</dd></div>
              <div><dt>Тривалість</dt><dd>45 хв</dd></div>
              <div><dt>Кабінет</dt><dd>№ 1</dd></div>
            </dl>
            <Link className="button button--secondary button--full" to="/patients">
              Відкрити картку
            </Link>
          </section>

          <section className="panel tasks-card" aria-labelledby="tasks-heading">
            <header className="panel__heading">
              <div>
                <p className="eyebrow">Справи</p>
                <h2 id="tasks-heading">2 із 4 виконано</h2>
              </div>
              <Link className="icon-button" to="/work-items" aria-label="Відкрити справи">
                <Icon name="chevron" />
              </Link>
            </header>
            <div className="progress" aria-label="Виконано 50 відсотків" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={50}>
              <span />
            </div>
            <ul className="task-list">
              <li><span className="task-check task-check--done">✓</span><span><strong>Підтвердити запис</strong><small>до 10:30</small></span></li>
              <li><span className="task-check" /><span><strong>Передзвонити пацієнту</strong><small>до 14:00</small></span></li>
            </ul>
          </section>
        </div>
      </div>
    </>
  );
}

export function ModulePreviewPage({ route }: { readonly route: AppRouteDefinition }) {
  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Модуль · preview</p>
          <h1>{route.label}</h1>
          <p>{route.description}. Реальні API та рольові проєкції з’являться у відповідному task packet.</p>
        </div>
        <Link className="button button--primary" to="/previews/empty">
          <Icon name="plus" />
          Переглянути empty state
        </Link>
      </header>
      <StatePreviewLinks />
      <section className="module-preview panel" aria-label={`Прев’ю модуля ${route.label}`}>
        <div className="module-preview__toolbar">
          <span className="module-preview__search"><Icon name="search" /> Пошук у модулі</span>
          <span className="module-preview__filter">Фільтри</span>
        </div>
        <div className="module-preview__grid" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
          <span />
          <span />
        </div>
        <div className="module-preview__notice">
          <Icon name="lock" />
          <span>
            <strong>Сервер залишається джерелом доступу</strong>
            <small>Route registry керує лише розміщенням і навігацією shell.</small>
          </span>
        </div>
      </section>
    </>
  );
}

type LiveResult = ContractSuccess | ErrorEnvelope;

export function ContractLabPage() {
  const [liveResult, setLiveResult] = useState<LiveResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function verifyLiveContract(outcome: "success" | "error") {
    setIsLoading(true);
    const { data, error } = await apiClient.GET("/api/v1/contract/fixture", {
      params: { query: { outcome } },
    });
    setLiveResult(data ?? error);
    setIsLoading(false);
  }

  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Platform · TP-102</p>
          <h1>API contract lab</h1>
          <p>Success і error fixtures типізовані безпосередньо з OpenAPI.</p>
        </div>
        <a className="button button--secondary" href="/api/v1/schema">
          Відкрити OpenAPI schema
        </a>
      </header>
      <section className="fixture-grid" aria-label="Contract fixtures">
        <article className="fixture-card fixture-card--success">
          <div className="fixture-card__heading"><span>200</span><h2>Success fixture</h2></div>
          <pre>{JSON.stringify(successFixture, null, 2)}</pre>
          <button className="button button--primary" type="button" disabled={isLoading} onClick={() => { void verifyLiveContract("success"); }}>
            Перевірити live success
          </button>
        </article>
        <article className="fixture-card fixture-card--error">
          <div className="fixture-card__heading"><span>422</span><h2>Error envelope</h2></div>
          <pre>{JSON.stringify(errorFixture, null, 2)}</pre>
          <button className="button button--primary" type="button" disabled={isLoading} onClick={() => { void verifyLiveContract("error"); }}>
            Перевірити live error
          </button>
        </article>
      </section>
      <section className="live-result panel" aria-live="polite">
        <h2>Live response</h2>
        {isLoading ? <p>Перевірка…</p> : null}
        {!isLoading && liveResult === null ? <p>Оберіть один із fixtures.</p> : null}
        {!isLoading && liveResult !== null ? <pre>{JSON.stringify(liveResult, null, 2)}</pre> : null}
      </section>
    </>
  );
}
