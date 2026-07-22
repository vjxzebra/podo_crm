import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
  type SyntheticEvent,
} from "react";
import { Link, useSearchParams } from "react-router";

import { Icon } from "../app/Icon";
import {
  getAuditEvent,
  listAuditActors,
  listAuditEvents,
  type AuditActorOption,
  type AuditEventDetail,
  type AuditEventListItem,
  type AuditListQuery,
  type AuditSection,
} from "./auditApi";
import {
  auditActionLabel,
  auditFieldLabel,
  auditInitials,
  auditObjectLink,
  auditRoleLabel,
  auditSectionLabel,
  auditSectionOptions,
  formatAuditDateTime,
  formatAuditListTime,
  formatAuditValue,
} from "./auditPresentation";

function useMobileAuditLayout(): boolean {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth <= 720);
  useEffect(() => {
    const update = () => { setIsMobile(window.innerWidth <= 720); };
    update();
    window.addEventListener("resize", update);
    return () => { window.removeEventListener("resize", update); };
  }, []);
  return isMobile;
}

function timeZoneOffsetMilliseconds(value: Date): number {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      day: "2-digit",
      hour: "2-digit",
      hourCycle: "h23",
      minute: "2-digit",
      month: "2-digit",
      second: "2-digit",
      timeZone: "Europe/Kyiv",
      year: "numeric",
    }).formatToParts(value).map((part) => [part.type, part.value]),
  );
  return Date.UTC(
    Number(parts.year),
    Number(parts.month) - 1,
    Number(parts.day),
    Number(parts.hour),
    Number(parts.minute),
    Number(parts.second),
  ) - value.getTime();
}

function kyivMidnight(date: string): number {
  const [year = 0, month = 0, day = 0] = date.split("-").map(Number);
  const desired = Date.UTC(year, month - 1, day);
  let candidate = desired;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    candidate = desired - timeZoneOffsetMilliseconds(new Date(candidate));
  }
  return candidate;
}

function nextDate(date: string): string {
  const [year = 0, month = 0, day = 0] = date.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + 1)).toISOString().slice(0, 10);
}

function queryFromFilters(
  search: string,
  actorId: string,
  section: "" | AuditSection,
  date: string,
): AuditListQuery {
  const trimmedSearch = search.trim();
  return {
    ...(trimmedSearch === "" ? {} : { search: trimmedSearch }),
    ...(actorId === "" ? {} : { actor_id: Number(actorId) }),
    ...(section === "" ? {} : { section }),
    ...(date === "" ? {} : {
      date_from: new Date(kyivMidnight(date)).toISOString(),
      date_to: new Date(kyivMidnight(nextDate(date)) - 1).toISOString(),
    }),
  };
}

function eventFailureMessage(message: string): string {
  return message.trim() || "Не вдалося завантажити журнал. Спробуйте ще раз.";
}

function resultLabel(result: string): string {
  return result === "success" ? "Успішно" : result;
}

interface AuditDetailPanelProps {
  readonly detail: AuditEventDetail | null;
  readonly error: string | null;
  readonly isLoading: boolean;
  readonly isMobile: boolean;
  readonly onClose: () => void;
  readonly onRetry: () => void;
  readonly selectedEventId: string;
  readonly panelRef: RefObject<HTMLElement | null>;
}

function AuditDetailPanel({
  detail,
  error,
  isLoading,
  isMobile,
  onClose,
  onRetry,
  panelRef,
  selectedEventId,
}: AuditDetailPanelProps) {
  const objectLink = detail === null ? null : auditObjectLink(detail.object);
  return (
    <aside
      aria-labelledby="audit-detail-title"
      aria-modal={isMobile ? "true" : undefined}
      className={`audit-detail${isMobile ? " audit-detail--mobile" : ""}`}
      ref={panelRef}
      role={isMobile ? "dialog" : "region"}
    >
      <header className="audit-detail__header">
        <div className="audit-detail__identity">
          <span className="audit-detail__icon"><Icon name="audit" /></span>
          <span>
            <small>Подія {selectedEventId.slice(0, 8).toLocaleUpperCase()}</small>
            <h2 id="audit-detail-title">{detail === null ? "Деталі події" : auditActionLabel(detail.action)}</h2>
          </span>
        </div>
        <button aria-label="Закрити деталі події" className="icon-button audit-detail__close" onClick={onClose} type="button"><Icon name="close" /></button>
      </header>

      {isLoading ? (
        <div aria-label="Завантаження деталей події" className="audit-detail__loading" role="status"><span /><span /><span /></div>
      ) : null}

      {!isLoading && error !== null ? (
        <div className="audit-detail__state" role="alert">
          <Icon name="warning" />
          <h3>Не вдалося відкрити подію</h3>
          <p>{error}</p>
          <button className="button button--secondary" onClick={onRetry} type="button"><Icon name="refresh" />Повторити</button>
        </div>
      ) : null}

      {!isLoading && error === null && detail !== null ? (
        <div className="audit-detail__content">
          <div className="audit-detail__status-row">
            <span className={`audit-section-tag audit-section-tag--${detail.section}`}>{auditSectionLabel(detail.section)}</span>
            <span className="audit-result-tag"><Icon name="check" />{resultLabel(detail.result ?? "success")}</span>
          </div>

          <dl className="audit-detail__meta">
            <div><dt>Хто виконав</dt><dd><span className="avatar" aria-hidden="true">{auditInitials(detail.actor.display_name)}</span><span><strong>{detail.actor.display_name}</strong><small>{auditRoleLabel(detail.actor.role)}{detail.actor.email === "" ? "" : ` · ${detail.actor.email}`}</small></span></dd></div>
            <div><dt>Дата й час</dt><dd><strong>{formatAuditDateTime(detail.occurred_at)}</strong><small>Повний час події у Europe/Kyiv</small></dd></div>
            <div><dt>Об’єкт зміни</dt><dd><strong>{detail.object.label}</strong><small>{detail.object.type} · {detail.object.id}</small></dd></div>
          </dl>

          <section className="audit-detail__description" aria-label="Опис події">
            <span>Опис</span>
            <p>{detail.description === undefined || detail.description.trim() === "" ? "Додатковий опис не вказано." : detail.description}</p>
          </section>

          <section className="audit-changes" aria-labelledby="audit-changes-title">
            <header><div><span>Незмінний diff</span><h3 id="audit-changes-title">Що змінилося</h3></div><b>{detail.changes.length}</b></header>
            {detail.changes.length === 0 ? (
              <div className="audit-changes__empty"><Icon name="empty" /><p><strong>Змінені поля не зафіксовані</strong><small>Подія описує дію без значущого before/after diff або містить однаково приховані значення.</small></p></div>
            ) : (
              <div className="audit-change-list">
                {detail.changes.map((change) => (
                  <article className="audit-change-card" key={change.field}>
                    <h4>{auditFieldLabel(change.field)}</h4>
                    <div>
                      <section><span>Було</span><pre>{formatAuditValue(change.before)}</pre></section>
                      <Icon name="chevron" />
                      <section className="audit-change-card__after"><span>Стало</span><pre>{formatAuditValue(change.after)}</pre></section>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="audit-detail__context">
            <Icon name="lock" />
            <p><strong>Службовий контекст</strong><small>{detail.note === undefined || detail.note.trim() === "" ? "Службову примітку не додано." : detail.note}</small><code>{detail.correlation_id}</code></p>
          </section>

          <footer className="audit-detail__footer">
            <span><Icon name="lock" />Запис захищений від змін</span>
            {objectLink === null ? null : <Link className="button button--secondary" to={objectLink}>Відкрити об’єкт<Icon name="chevron" /></Link>}
          </footer>
        </div>
      ) : null}
    </aside>
  );
}

export function AuditPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const isMobile = useMobileAuditLayout();
  const [search, setSearch] = useState("");
  const [actorId, setActorId] = useState("");
  const [section, setSection] = useState<"" | AuditSection>("");
  const [date, setDate] = useState("");
  const [query, setQuery] = useState<AuditListQuery>({});
  const [events, setEvents] = useState<readonly AuditEventListItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [actors, setActors] = useState<readonly AuditActorOption[]>([]);
  const [actorsError, setActorsError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [detail, setDetail] = useState<AuditEventDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const listSequence = useRef(0);
  const rowRefs = useRef(new Map<string, HTMLButtonElement>());
  const detailPanelRef = useRef<HTMLElement>(null);

  const selectedEventId = searchParams.get("event");
  const filtersActive = useMemo(() => Object.keys(query).length > 0, [query]);

  const loadActors = useCallback(async (signal?: AbortSignal) => {
    try {
      const result = await listAuditActors(signal);
      if (signal?.aborted) return;
      if (!result.ok) {
        setActorsError(eventFailureMessage(result.error.message));
        return;
      }
      setActors(result.data);
      setActorsError(null);
    } catch (reason: unknown) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setActorsError("Не вдалося завантажити список працівників.");
    }
  }, []);

  const loadEvents = useCallback(async (
    requestedQuery: AuditListQuery,
    cursor?: string,
    signal?: AbortSignal,
  ) => {
    const sequence = listSequence.current + 1;
    listSequence.current = sequence;
    if (cursor === undefined) {
      setIsLoading(true);
      setListError(null);
    } else {
      setIsLoadingMore(true);
    }
    try {
      const result = await listAuditEvents(requestedQuery, cursor, signal);
      if (sequence !== listSequence.current || signal?.aborted) return;
      if (!result.ok) {
        setListError(eventFailureMessage(result.error.message));
        return;
      }
      setEvents((current) => cursor === undefined ? result.data.events : [...current, ...result.data.events]);
      setNextCursor(result.data.next_cursor);
      setListError(null);
    } catch (reason: unknown) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (sequence === listSequence.current) setListError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } finally {
      if (sequence === listSequence.current) {
        setIsLoading(false);
        setIsLoadingMore(false);
      }
    }
  }, []);

  const loadDetail = useCallback(async (eventId: string, signal?: AbortSignal) => {
    setIsDetailLoading(true);
    setDetailError(null);
    setDetail(null);
    try {
      const result = await getAuditEvent(eventId, signal);
      if (signal?.aborted) return;
      if (!result.ok) {
        setDetailError(eventFailureMessage(result.error.message));
        return;
      }
      setDetail(result.data);
    } catch (reason: unknown) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setDetailError("Немає зв’язку із сервером. Деталі не завантажено.");
    } finally {
      if (!signal?.aborted) setIsDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadActors(controller.signal);
    return () => { controller.abort(); };
  }, [loadActors]);

  useEffect(() => {
    const controller = new AbortController();
    void loadEvents(query, undefined, controller.signal);
    return () => { controller.abort(); };
  }, [loadEvents, query]);

  useEffect(() => {
    if (selectedEventId === null) {
      setDetail(null);
      setDetailError(null);
      setIsDetailLoading(false);
      return;
    }
    const controller = new AbortController();
    void loadDetail(selectedEventId, controller.signal);
    return () => { controller.abort(); };
  }, [loadDetail, selectedEventId]);

  const closeDetail = useCallback(() => {
    const eventId = selectedEventId;
    const next = new URLSearchParams(searchParams);
    next.delete("event");
    setSearchParams(next, { replace: true });
    if (eventId !== null) window.setTimeout(() => { rowRefs.current.get(eventId)?.focus(); }, 0);
  }, [searchParams, selectedEventId, setSearchParams]);

  useEffect(() => {
    if (selectedEventId === null) return;
    const previousOverflow = document.body.style.overflow;
    if (isMobile) {
      document.body.style.overflow = "hidden";
      window.setTimeout(() => {
        detailPanelRef.current?.querySelector<HTMLButtonElement>(".audit-detail__close")?.focus();
      }, 0);
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeDetail();
        return;
      }
      if (!isMobile || event.key !== "Tab") return;
      const focusable = [...(detailPanelRef.current?.querySelectorAll<HTMLElement>("button:not(:disabled), a[href]") ?? [])];
      const first = focusable[0];
      const last = focusable.at(-1);
      if (first === undefined || last === undefined) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (isMobile) document.body.style.overflow = previousOverflow;
    };
  }, [closeDetail, isMobile, selectedEventId]);

  const applyFilters = (event?: SyntheticEvent<HTMLFormElement>) => {
    event?.preventDefault();
    setQuery(queryFromFilters(search, actorId, section, date));
  };

  const clearFilters = () => {
    setSearch("");
    setActorId("");
    setSection("");
    setDate("");
    setQuery({});
  };

  const openEvent = (event: AuditEventListItem, trigger: HTMLButtonElement) => {
    rowRefs.current.set(event.id, trigger);
    const next = new URLSearchParams(searchParams);
    next.set("event", event.id);
    setSearchParams(next);
  };

  const refresh = () => {
    void loadEvents(query);
    void loadActors();
    if (selectedEventId !== null) void loadDetail(selectedEventId);
  };

  return (
    <>
      <header className="page-heading audit-heading">
        <div><p className="eyebrow">Контроль і безпека · TP-803</p><h1>Журнал дій</h1><p>Незмінна історія записів, пацієнтів, прийомів, оплат, складу та доступу працівників.</p></div>
        <span className="audit-owner-badge"><Icon name="lock" />Тільки адмін / власник</span>
      </header>

      <section className="panel audit-toolbar-panel" aria-label="Фільтри журналу">
        <form className="audit-toolbar" onSubmit={applyFilters} role="search">
          <label className="audit-search"><span>Пошук</span><div><Icon name="search" /><input aria-label="Пошук у журналі" onChange={(event) => { setSearch(event.target.value); }} placeholder="Дія, об’єкт, працівник або номер" value={search} /></div></label>
          <label><span>Працівник</span><select aria-label="Працівник" disabled={actors.length === 0 && actorsError === null} onChange={(event) => { setActorId(event.target.value); }} value={actorId}><option value="">Усі працівники</option>{actors.map((actor) => <option key={actor.id} value={actor.id}>{actor.display_name}{actor.is_active ? "" : " · неактивний"}</option>)}</select></label>
          <label><span>Розділ</span><select aria-label="Розділ журналу" onChange={(event) => { setSection(event.target.value as "" | AuditSection); }} value={section}><option value="">Усі розділи</option>{auditSectionOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          <label><span>Дата</span><input aria-label="Дата події" onChange={(event) => { setDate(event.target.value); }} type="date" value={date} /></label>
          <div className="audit-toolbar__actions"><button className="button button--primary" disabled={isLoading} type="submit">Застосувати</button><button className="button button--secondary" disabled={!filtersActive && search === "" && actorId === "" && section === "" && date === ""} onClick={clearFilters} type="button">Скинути</button><button aria-label="Оновити журнал" className="icon-button" disabled={isLoading} onClick={refresh} type="button"><Icon name="refresh" /></button></div>
        </form>
        {actorsError === null ? null : <div className="audit-toolbar__warning" role="status"><Icon name="warning" /><span>{actorsError} Фільтр за працівником тимчасово недоступний.</span><button onClick={() => { void loadActors(); }} type="button">Повторити</button></div>}
      </section>

      <section className={`audit-layout${selectedEventId === null ? " audit-layout--no-detail" : ""}`}>
        <article className="panel audit-log" aria-labelledby="audit-log-title">
          <header className="audit-log__header"><div><h2 id="audit-log-title">Події CRM</h2><p>Найновіші дії показані першими.</p></div><span>{events.length} завантажено</span></header>

          {isLoading && events.length === 0 ? <div aria-label="Завантаження журналу" className="audit-list-loading" role="status"><span /><span /><span /><span /></div> : null}

          {!isLoading && listError !== null && events.length === 0 ? <div className="audit-state" role="alert"><Icon name="warning" /><h3>Не вдалося завантажити журнал</h3><p>{listError}</p><button className="button button--primary" onClick={() => { void loadEvents(query); }} type="button"><Icon name="refresh" />Повторити</button></div> : null}

          {!isLoading && listError === null && events.length === 0 ? <div className="audit-state"><Icon name="empty" /><h3>{filtersActive ? "Подій за фільтрами не знайдено" : "Журнал поки порожній"}</h3><p>{filtersActive ? "Змініть критерії або скиньте фільтри." : "Після першої критичної дії подія з’явиться тут автоматично."}</p>{filtersActive ? <button className="button button--secondary" onClick={clearFilters} type="button">Скинути фільтри</button> : null}</div> : null}

          {events.length > 0 ? (
            <div className="audit-list">
              <div aria-hidden="true" className="audit-list__head"><span>Час</span><span>Працівник</span><span>Розділ</span><span>Дія та об’єкт</span><span>Результат</span></div>
              {events.map((event) => (
                <button
                  aria-label={`Відкрити подію: ${auditActionLabel(event.action)} — ${event.object.label}`}
                  aria-pressed={selectedEventId === event.id}
                  className={`audit-row${selectedEventId === event.id ? " audit-row--selected" : ""}`}
                  key={event.id}
                  onClick={(clickEvent) => { openEvent(event, clickEvent.currentTarget); }}
                  ref={(element) => { if (element === null) rowRefs.current.delete(event.id); else rowRefs.current.set(event.id, element); }}
                  type="button"
                >
                  <time dateTime={event.occurred_at}>{formatAuditListTime(event.occurred_at)}</time>
                  <span className="audit-row__actor"><span className="avatar" aria-hidden="true">{auditInitials(event.actor.display_name)}</span><span><strong>{event.actor.display_name}</strong><small>{auditRoleLabel(event.actor.role)}</small></span></span>
                  <span><b className={`audit-section-tag audit-section-tag--${event.section}`}>{auditSectionLabel(event.section)}</b></span>
                  <span className="audit-row__event"><strong>{auditActionLabel(event.action)}</strong><small>{event.object.label}</small></span>
                  <span className="audit-row__result"><b><Icon name="check" />{resultLabel(event.result ?? "success")}</b><Icon name="chevron" /></span>
                </button>
              ))}
            </div>
          ) : null}

          {listError !== null && events.length > 0 ? <div className="audit-inline-error" role="alert"><span>{listError}</span><button onClick={() => { void loadEvents(query); }} type="button">Оновити список</button></div> : null}

          <footer className="audit-log__footer"><span><Icon name="lock" />Події не можна редагувати або видаляти.</span>{nextCursor === null ? null : <button className="button button--secondary" disabled={isLoadingMore} onClick={() => { void loadEvents(query, nextCursor); }} type="button">{isLoadingMore ? "Завантажуємо…" : "Показати старіші"}</button>}</footer>
        </article>

        {selectedEventId === null ? <aside className="panel audit-detail-placeholder"><Icon name="audit" /><h2>Оберіть подію</h2><p>Відкрийте рядок журналу, щоб переглянути redacted diff «Було → Стало» та службовий контекст.</p><span><Icon name="lock" />Лише читання</span></aside> : <AuditDetailPanel detail={detail} error={detailError} isLoading={isDetailLoading} isMobile={isMobile} onClose={closeDetail} onRetry={() => { void loadDetail(selectedEventId); }} panelRef={detailPanelRef} selectedEventId={selectedEventId} />}
      </section>
    </>
  );
}
