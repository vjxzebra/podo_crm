import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";

import { apiClient } from "../api/client";
import type { components, operations } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders, useAuth } from "../auth/AuthContext";
import { WorkItemCreateDialog } from "./WorkItemCreateDialog";

type WorkItem = components["schemas"]["WorkItem"];
type WorkItemAssignee = components["schemas"]["WorkItemAssignee"];
type WorkItemSummary = components["schemas"]["WorkItemSummary"];
type WorkItemUpdate = NonNullable<operations["work_item_update"]["requestBody"]>["content"]["application/json"];
type WorkItemScope = "own" | "all";
type WorkItemStatus = "open" | "completed" | "all";

const emptySummary: WorkItemSummary = { open: 0, completed: 0, overdue: 0, important: 0 };

function formatDueAt(value: string): { readonly date: string; readonly time: string } {
  const date = new Date(value);
  return {
    date: new Intl.DateTimeFormat("uk-UA", {
      day: "numeric",
      month: "long",
      timeZone: "Europe/Kyiv",
    }).format(date),
    time: new Intl.DateTimeFormat("uk-UA", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Europe/Kyiv",
    }).format(date),
  };
}

export function WorkItemsPage() {
  const { state } = useAuth();
  const role = state.status === "authenticated" ? state.session.user.role : "podologist";
  const canViewAll = role !== "podologist";
  const [scope, setScope] = useState<WorkItemScope>("own");
  const [status, setStatus] = useState<WorkItemStatus>("open");
  const [search, setSearch] = useState("");
  const [items, setItems] = useState<readonly WorkItem[]>([]);
  const [summary, setSummary] = useState<WorkItemSummary>(emptySummary);
  const [assignees, setAssignees] = useState<readonly WorkItemAssignee[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [mutatingId, setMutatingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const loadWorkItems = useCallback(async (
    requestedScope: WorkItemScope,
    requestedStatus: WorkItemStatus,
    query: string,
  ) => {
    setIsLoading(true);
    setError(null);
    const result = await apiClient.GET("/api/v1/work-items", {
      params: {
        query: {
          scope: requestedScope,
          status: requestedStatus,
          ...(query.trim() ? { search: query.trim() } : {}),
        },
      },
    }).catch(() => null);
    setIsLoading(false);
    if (result === null) {
      setError("Не вдалося зв’язатися із сервером.");
      return;
    }
    if (result.data === undefined) {
      setError(result.error.message);
      return;
    }
    setItems(result.data.work_items);
    setSummary(result.data.summary);
    setAssignees(result.data.assignees);
    if (result.data.effective_scope !== requestedScope) {
      setScope(result.data.effective_scope);
    }
  }, []);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void loadWorkItems(scope, status, search);
    }, search ? 250 : 0);
    return () => { window.clearTimeout(timeout); };
  }, [loadWorkItems, scope, search, status]);

  const toggleCompletion = async (item: WorkItem) => {
    const completing = !item.is_completed;
    setMutatingId(item.id);
    setError(null);
    setSuccess(null);
    const body: WorkItemUpdate = {
      version: item.version ?? 1,
      is_completed: completing,
    };
    const result = await apiClient.PATCH("/api/v1/work-items/{work_item_id}", {
      params: { path: { work_item_id: item.id } },
      body,
      headers: csrfHeaders(),
    }).catch(() => null);
    setMutatingId(null);
    if (result === null) {
      setError("Не вдалося зв’язатися із сервером.");
      return;
    }
    if (result.data === undefined) {
      setError(result.error.message);
      return;
    }
    const updated = result.data;
    setItems((current) => current.flatMap((currentItem) => {
      if (currentItem.id !== updated.id) {
        return [currentItem];
      }
      if (status === "all" || Boolean(updated.is_completed) === (status === "completed")) {
        return [updated];
      }
      return [];
    }));
    setSummary((current) => ({
      open: current.open + (completing ? -1 : 1),
      completed: current.completed + (completing ? 1 : -1),
      overdue: current.overdue + (item.is_overdue ? -1 : 0),
      important: current.important + (item.is_important ? completing ? -1 : 1 : 0),
    }));
    setSuccess(completing ? `Справу «${item.title}» виконано.` : `Справу «${item.title}» повернуто в роботу.`);
  };

  return (
    <>
      <header className="page-heading work-items-heading">
        <div><p className="eyebrow">Команда · TP-303</p><h1>Внутрішні справи</h1><p>Дзвінки, підтвердження, ручні повідомлення та інші задачі з відповідальним і строком.</p></div>
        <button className="button button--primary" onClick={() => { setIsCreating(true); setSuccess(null); }} type="button"><Icon name="plus" />Нова справа</button>
      </header>
      {success ? <div className="form-message form-message--success" role="status"><Icon name="check" /><span>{success}</span></div> : null}
      <section className="work-item-summary" aria-label="Підсумок справ">
        <article><span>Відкриті</span><strong>{summary.open}</strong></article>
        <article><span>Прострочені</span><strong>{summary.overdue}</strong></article>
        <article><span>Важливі</span><strong>{summary.important}</strong></article>
        <article><span>Виконані</span><strong>{summary.completed}</strong></article>
      </section>
      <section className="panel work-items-panel" aria-labelledby="work-items-list-title">
        <div className="work-items-toolbar">
          <label className="patient-search work-item-search"><Icon name="search" /><span className="visually-hidden">Пошук справ</span><input onChange={(event) => { setSearch(event.target.value); setSuccess(null); }} placeholder="Назва, коментар або пацієнт" type="search" value={search} /></label>
          {canViewAll ? <div className="segmented-control" aria-label="Обсяг справ"><button className={scope === "own" ? "active" : ""} onClick={() => { setScope("own"); setSuccess(null); }} type="button">Мої</button><button className={scope === "all" ? "active" : ""} onClick={() => { setScope("all"); setSuccess(null); }} type="button">Усі команди</button></div> : <span className="patient-scope-pill"><Icon name="lock" />Лише мої справи</span>}
          <button aria-label="Оновити справи" className="icon-button" onClick={() => void loadWorkItems(scope, status, search)} type="button"><Icon name="refresh" /></button>
        </div>
        <header className="work-items-list-header">
          <div><h2 id="work-items-list-title">Список справ</h2><span>{isLoading ? "Оновлення…" : `Показано: ${String(items.length)}`}</span></div>
          <div className="segmented-control" aria-label="Стан справ">{([{"id":"open","label":"Відкриті"},{"id":"completed","label":"Виконані"},{"id":"all","label":"Усі"}] as const).map((option) => <button className={status === option.id ? "active" : ""} key={option.id} onClick={() => { setStatus(option.id); setSuccess(null); }} type="button">{option.label}</button>)}</div>
        </header>
        {error ? <div className="patient-list-message patient-list-message--error" role="alert"><Icon name="warning" /><span><strong>Не вдалося оновити справи</strong><small>{error}</small></span><button className="button button--secondary" onClick={() => void loadWorkItems(scope, status, search)} type="button">Повторити</button></div> : null}
        {isLoading && items.length === 0 ? <div className="work-item-skeletons" aria-label="Завантаження справ"><span /><span /><span /></div> : null}
        {!isLoading && !error && items.length === 0 ? <div className="patient-empty work-item-empty"><span className="patient-empty__icon"><Icon name="tasks" /></span><h2>{search ? "Справ за запитом не знайдено" : status === "completed" ? "Виконаних справ ще немає" : "Відкритих справ немає"}</h2><p>{search ? "Змініть пошук або фільтр." : "Створіть нову внутрішню справу для себе чи колеги."}</p><button className="button button--primary" onClick={() => { setIsCreating(true); }} type="button"><Icon name="plus" />Створити справу</button></div> : null}
        {items.length ? <div className="work-item-list">{items.map((item) => {
          const due = formatDueAt(item.due_at);
          return <article className={`work-item-card${item.is_important ? " work-item-card--important" : ""}${item.is_overdue ? " work-item-card--overdue" : ""}${item.is_completed ? " work-item-card--completed" : ""}`} key={item.id}>
            <button aria-label={item.is_completed ? `Повернути в роботу: ${item.title}` : `Позначити виконаною: ${item.title}`} className="work-item-complete" disabled={mutatingId === item.id} onClick={() => void toggleCompletion(item)} type="button">{item.is_completed ? <Icon name="check" /> : null}</button>
            <div className="work-item-card__body"><header><span className="work-item-kind"><Icon name={item.kind === "callback" ? "phone" : "tasks"} />{item.kind_label}</span>{item.is_important ? <span className="work-item-important"><Icon name="flag" />Важлива</span> : null}</header><h3>{item.title}</h3>{item.comment ? <p>{item.comment}</p> : null}<div className="work-item-card__links">{item.patient ? <Link to={`/patients/${item.patient.id}/overview`}>{item.patient.display_name} · {item.patient.phone}</Link> : <span>Без пацієнта</span>}<span>Відповідальний: {item.assignee.display_name}</span></div></div>
            <time className="work-item-due" dateTime={item.due_at}><strong>{due.time}</strong><span>{due.date}</span>{item.is_overdue ? <em>Прострочено</em> : null}</time>
          </article>;
        })}</div> : null}
      </section>
      {isCreating ? <WorkItemCreateDialog assignees={assignees} onClose={() => { setIsCreating(false); }} onSaved={(item) => { setIsCreating(false); setSuccess(`Справу «${item.title}» створено.`); void loadWorkItems(scope, status, search); }} /> : null}
    </>
  );
}
