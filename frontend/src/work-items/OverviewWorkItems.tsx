import { useEffect, useState } from "react";
import { Link } from "react-router";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";

type WorkItem = components["schemas"]["WorkItem"];
type WorkItemSummary = components["schemas"]["WorkItemSummary"];

const emptySummary: WorkItemSummary = { open: 0, completed: 0, overdue: 0, important: 0 };

function dueTime(value: string): string {
  return new Intl.DateTimeFormat("uk-UA", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Kyiv",
  }).format(new Date(value));
}

export function OverviewWorkItems() {
  const [items, setItems] = useState<readonly WorkItem[]>([]);
  const [summary, setSummary] = useState<WorkItemSummary>(emptySummary);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    const load = async () => {
      const result = await apiClient.GET("/api/v1/work-items", {
        params: { query: { scope: "own", status: "all" } },
      }).catch(() => null);
      setIsLoading(false);
      if (!Array.isArray(result?.data?.work_items)) {
        setHasError(true);
        return;
      }
      setItems(result.data.work_items.slice(0, 3));
      setSummary(result.data.summary);
    };
    void load();
  }, []);

  const total = summary.open + summary.completed;
  const progress = total === 0 ? 0 : Math.round((summary.completed / total) * 100);
  return (
    <section className="panel tasks-card" aria-labelledby="tasks-heading">
      <header className="panel__heading">
        <div><p className="eyebrow">Справи</p><h2 id="tasks-heading">{isLoading ? "Оновлюємо…" : `${String(summary.completed)} із ${String(total)} виконано`}</h2></div>
        <Link className="icon-button" to="/work-items" aria-label="Відкрити справи"><Icon name="chevron" /></Link>
      </header>
      <div aria-label={`Виконано ${String(progress)} відсотків`} aria-valuemax={100} aria-valuemin={0} aria-valuenow={progress} className="progress" role="progressbar"><span style={{ width: `${String(progress)}%` }} /></div>
      {hasError ? <p className="overview-tasks-state">Не вдалося завантажити справи.</p> : null}
      {!isLoading && !hasError && items.length === 0 ? <p className="overview-tasks-state">Власних справ ще немає.</p> : null}
      {items.length ? <ul className="task-list">{items.map((item) => <li key={item.id}><span className={`task-check${item.is_completed ? " task-check--done" : ""}`}>{item.is_completed ? "✓" : ""}</span><span><strong>{item.title}</strong><small>{item.is_completed ? "Виконано" : `${item.is_overdue ? "Прострочено · " : "до "}${dueTime(item.due_at)}`}</small></span></li>)}</ul> : null}
    </section>
  );
}
