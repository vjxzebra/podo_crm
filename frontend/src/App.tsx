import { useState } from "react";

import { apiClient } from "./api/client";
import {
  errorFixture,
  successFixture,
  type ContractSuccess,
  type ErrorEnvelope,
} from "./contractFixtures";

type LiveResult = ContractSuccess | ErrorEnvelope;

export function App() {
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
    <main className="page-shell">
      <header className="hero">
        <p className="eyebrow">Podoria CRM · TP-102</p>
        <h1>API contract lab</h1>
        <p>
          Success і error fixtures типізовані безпосередньо з OpenAPI. Наступний етап
          використає цей клієнт у responsive application shell.
        </p>
        <a href="/api/v1/schema">Відкрити OpenAPI schema</a>
      </header>

      <section className="fixture-grid" aria-label="Contract fixtures">
        <article className="fixture-card fixture-card--success">
          <div className="fixture-card__heading">
            <span>200</span>
            <h2>Success fixture</h2>
          </div>
          <pre>{JSON.stringify(successFixture, null, 2)}</pre>
          <button
            type="button"
            disabled={isLoading}
            onClick={() => {
              void verifyLiveContract("success");
            }}
          >
            Перевірити live success
          </button>
        </article>

        <article className="fixture-card fixture-card--error">
          <div className="fixture-card__heading">
            <span>422</span>
            <h2>Error envelope</h2>
          </div>
          <pre>{JSON.stringify(errorFixture, null, 2)}</pre>
          <button
            type="button"
            disabled={isLoading}
            onClick={() => {
              void verifyLiveContract("error");
            }}
          >
            Перевірити live error
          </button>
        </article>
      </section>

      <section className="live-result" aria-live="polite">
        <h2>Live response</h2>
        {isLoading ? <p>Перевірка…</p> : null}
        {!isLoading && liveResult === null ? <p>Оберіть один із fixtures.</p> : null}
        {!isLoading && liveResult !== null ? (
          <pre>{JSON.stringify(liveResult, null, 2)}</pre>
        ) : null}
      </section>
    </main>
  );
}
