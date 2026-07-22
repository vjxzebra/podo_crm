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
