import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useSearchParams } from "react-router";

import { Icon } from "../app/Icon";
import { useModalLifecycle } from "../app/useModalLifecycle";
import {
  getBookingRequest,
  listBookingRequests,
  processBookingRequest,
  type BookingRequest,
  type BookingRequestCounts,
  type BookingRequestSource,
  type BookingRequestStatus,
} from "./bookingRequestApi";

const emptyCounts: BookingRequestCounts = { new: 0, processed: 0, total: 0 };

const sourceOptions: readonly {
  readonly value: BookingRequestSource;
  readonly label: string;
}[] = [
  { value: "ALL", label: "Усі джерела" },
  { value: "INSTAGRAM", label: "Instagram" },
  { value: "FACEBOOK", label: "Facebook" },
  { value: "WEBSITE", label: "Сайт" },
];

const statusOptions: readonly {
  readonly value: BookingRequestStatus;
  readonly label: string;
}[] = [
  { value: "NEW", label: "Нові" },
  { value: "PROCESSED", label: "Оброблені" },
  { value: "ALL", label: "Усі" },
];

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("uk-UA", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Europe/Kyiv",
  }).format(new Date(value));
}

function formatShortDateTime(value: string): {
  readonly date: string;
  readonly time: string;
} {
  const date = new Date(value);
  return {
    date: new Intl.DateTimeFormat("uk-UA", {
      day: "2-digit",
      month: "short",
      timeZone: "Europe/Kyiv",
    }).format(date),
    time: new Intl.DateTimeFormat("uk-UA", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Europe/Kyiv",
    }).format(date),
  };
}

function apiFailure(message: string): string {
  return message.trim() || "Не вдалося виконати дію. Спробуйте ще раз.";
}

function nonEmpty(value: string | undefined, fallback: string): string {
  if (value === undefined || value.trim() === "") return fallback;
  return value;
}

function customerName(item: BookingRequest): string {
  return nonEmpty(item.client_name, "Ім’я не вказано");
}

function customerSummary(item: BookingRequest): string {
  const values = [item.phone, item.service, item.contact_handle]
    .map((value) => value?.trim() ?? "")
    .filter(Boolean);
  return values.length > 0 ? values.join(" · ") : "Контактні дані не вказано";
}

function RequestStatusBadge({ status }: { readonly status: BookingRequest["status"] }) {
  const isProcessed = status === "PROCESSED";
  return (
    <span className={`booking-request-status booking-request-status--${isProcessed ? "processed" : "new"}`}>
      <span aria-hidden="true" />
      {isProcessed ? "Оброблена" : "Нова"}
    </span>
  );
}

function SourceBadge({
  source,
  label,
}: {
  readonly source: BookingRequest["source"];
  readonly label: string;
}) {
  return (
    <span className={`booking-request-source booking-request-source--${source.toLocaleLowerCase()}`}>
      <span aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

function BookingRequestDetail({
  bookingRequestId,
  onClose,
  onProcessed,
}: {
  readonly bookingRequestId: string;
  readonly onClose: () => void;
  readonly onProcessed: (item: BookingRequest) => void;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const [item, setItem] = useState<BookingRequest | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useModalLifecycle({
    dialogRef,
    initialFocusRef: closeRef,
    onEscape: onClose,
  });

  const loadDetail = useCallback(async (
    signal?: AbortSignal,
    preserveError = false,
  ) => {
    setIsLoading(true);
    if (!preserveError) setError(null);
    try {
      const result = await getBookingRequest(bookingRequestId, signal);
      if (signal?.aborted) return;
      if (!result.ok) {
        setError(apiFailure(result.error.message));
        return;
      }
      setItem(result.data);
    } catch (reason: unknown) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setError("Немає зв’язку із сервером. Перевірте мережу та повторіть.");
    } finally {
      if (!signal?.aborted) setIsLoading(false);
    }
  }, [bookingRequestId]);

  useEffect(() => {
    const controller = new AbortController();
    void loadDetail(controller.signal);
    return () => { controller.abort(); };
  }, [loadDetail]);

  const markProcessed = async () => {
    if (item === null || isProcessing || item.status === "PROCESSED") return;
    setIsProcessing(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await processBookingRequest(item.id, item.version ?? 1);
      if (!result.ok) {
        if (result.status === 409) {
          setError("Заявку вже змінив інший працівник. Дані оновлено.");
          await loadDetail(undefined, true);
        } else {
          setError(apiFailure(result.error.message));
        }
        return;
      }
      setItem(result.data);
      setSuccess("Заявку позначено обробленою.");
      onProcessed(result.data);
    } catch {
      setError("Немає зв’язку із сервером. Статус заявки не змінено.");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="modal-layer booking-request-detail-layer" role="presentation">
      <section
        aria-labelledby="booking-request-detail-title"
        aria-modal="true"
        className="modal-card booking-request-detail"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <header className="modal-card__header">
          <div>
            <p className="eyebrow">Заявка на запис</p>
            <h2 id="booking-request-detail-title">
              {item?.public_number ?? "Завантаження…"}
            </h2>
            {item === null ? null : <p>Отримано {formatDateTime(item.created_at)}</p>}
          </div>
          <button
            aria-label="Закрити деталі заявки"
            className="icon-button"
            onClick={onClose}
            ref={closeRef}
            type="button"
          >
            <Icon name="close" />
          </button>
        </header>

        {isLoading && item === null ? (
          <div aria-label="Завантаження деталей заявки" className="booking-request-detail-skeleton" role="status">
            <span /><span /><span /><span />
          </div>
        ) : null}

        {error !== null ? (
          <div className="form-message form-message--error" role="alert">
            <Icon name="warning" />
            <span>{error}</span>
          </div>
        ) : null}
        {success !== null ? (
          <div className="form-message form-message--success" role="status">
            <Icon name="check" />
            <span>{success}</span>
          </div>
        ) : null}

        {!isLoading && item === null ? (
          <div className="booking-request-detail-error">
            <p>Деталі заявки недоступні.</p>
            <button className="button button--secondary" onClick={() => { void loadDetail(); }} type="button">
              <Icon name="refresh" />Повторити
            </button>
          </div>
        ) : null}

        {item === null ? null : (
          <>
            <div className="booking-request-detail__status">
              <RequestStatusBadge status={item.status} />
              <SourceBadge source={item.source} label={item.source_label} />
            </div>

            <dl className="booking-request-detail__grid">
              <div>
                <dt>Клієнт</dt>
                <dd>{customerName(item)}</dd>
              </div>
              <div>
                <dt>Телефон</dt>
                <dd>
                  {item.phone
                    ? <a href={`tel:${item.phone}`}>{item.phone}</a>
                    : "Не вказано"}
                </dd>
              </div>
              <div>
                <dt>Послуга</dt>
                <dd>{nonEmpty(item.service, "Не вказано")}</dd>
              </div>
              {item.contact_handle ? (
                <div>
                  <dt>Контакт у соцмережі</dt>
                  <dd>{item.contact_handle}</dd>
                </div>
              ) : null}
              {item.preferred_at ? (
                <div>
                  <dt>Бажаний час</dt>
                  <dd>{formatDateTime(item.preferred_at)}</dd>
                </div>
              ) : null}
            </dl>

            <section className="booking-request-detail__message" aria-labelledby="booking-request-message-title">
              <h3 id="booking-request-message-title">Коментар</h3>
              <p>{nonEmpty(item.message, "Коментар не вказано.")}</p>
            </section>

            {item.status === "PROCESSED" ? (
              <div className="booking-request-processed-note">
                <span><Icon name="check" /></span>
                <div>
                  <strong>Заявку оброблено</strong>
                  <p>
                    {nonEmpty(item.processed_by_display_name, "Працівник")}
                    {item.processed_at ? ` · ${formatDateTime(item.processed_at)}` : ""}
                  </p>
                </div>
              </div>
            ) : null}

            {item.external_reference ? (
              <p className="booking-request-reference">
                Ідентифікатор джерела: <code>{item.external_reference}</code>
              </p>
            ) : null}

            <footer className="modal-card__footer">
              <button className="button button--secondary" onClick={onClose} type="button">
                Закрити
              </button>
              {item.status === "NEW" ? (
                <button
                  className="button button--primary"
                  disabled={isProcessing}
                  onClick={() => { void markProcessed(); }}
                  type="button"
                >
                  <Icon name="check" />
                  {isProcessing ? "Обробляємо…" : "Заявка оброблена"}
                </button>
              ) : null}
            </footer>
          </>
        )}
      </section>
    </div>
  );
}

export function BookingRequestsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [status, setStatus] = useState<BookingRequestStatus>("NEW");
  const [source, setSource] = useState<BookingRequestSource>("ALL");
  const [search, setSearch] = useState("");
  const [items, setItems] = useState<readonly BookingRequest[]>([]);
  const [counts, setCounts] = useState<BookingRequestCounts>(emptyCounts);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestSequence = useRef(0);
  const selectedRequestId = searchParams.get("request");
  const query = useMemo(() => ({
    status,
    source,
    ...(search.trim() ? { search: search.trim() } : {}),
  }), [search, source, status]);

  const load = useCallback(async (
    requestedQuery: typeof query,
    cursor?: string,
    signal?: AbortSignal,
  ) => {
    const sequence = requestSequence.current + 1;
    requestSequence.current = sequence;
    if (cursor === undefined) {
      setIsLoading(true);
      setError(null);
    } else {
      setIsLoadingMore(true);
    }
    try {
      const result = await listBookingRequests(requestedQuery, cursor, signal);
      if (sequence !== requestSequence.current || signal?.aborted) return;
      if (!result.ok) {
        setError(apiFailure(result.error.message));
        return;
      }
      setItems((current) => cursor === undefined
        ? result.data.booking_requests
        : [...current, ...result.data.booking_requests]);
      setCounts(result.data.counts);
      setNextCursor(result.data.next_cursor);
      setError(null);
    } catch (reason: unknown) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (sequence === requestSequence.current) {
        setError("Немає зв’язку із сервером. Перевірте мережу та повторіть.");
      }
    } finally {
      if (sequence === requestSequence.current) {
        setIsLoading(false);
        setIsLoadingMore(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      void load(query, undefined, controller.signal);
    }, search.trim() ? 300 : 0);
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [load, query, search]);

  const openDetail = (id: string) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set("request", id);
      return next;
    });
  };

  const closeDetail = () => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("request");
      return next;
    }, { replace: true });
  };

  const onProcessed = (updated: BookingRequest) => {
    setItems((current) => {
      if (status === "NEW") return current.filter((item) => item.id !== updated.id);
      return current.map((item) => item.id === updated.id ? updated : item);
    });
    setCounts((current) => ({
      new: Math.max(0, current.new - 1),
      processed: current.processed + 1,
      total: current.total,
    }));
  };

  return (
    <>
      <header className="page-heading booking-requests-heading">
        <div>
          <p className="eyebrow">Комунікації · TP-1008</p>
          <h1>Заявки на запис</h1>
          <p>Звернення клієнтів з Instagram, Facebook і сайту в одному робочому списку.</p>
        </div>
        <button
          className="button button--secondary"
          disabled={isLoading}
          onClick={() => { void load(query); }}
          type="button"
        >
          <Icon name="refresh" />Оновити
        </button>
      </header>

      <section className="booking-request-summary" aria-label="Підсумок заявок">
        <article className="booking-request-summary__new">
          <span><i aria-hidden="true" />Нові</span>
          <strong>{counts.new}</strong>
          <small>очікують обробки</small>
        </article>
        <article>
          <span><Icon name="check" />Оброблені</span>
          <strong>{counts.processed}</strong>
          <small>завершені звернення</small>
        </article>
        <article>
          <span><Icon name="inbox" />Усього</span>
          <strong>{counts.total}</strong>
          <small>отримано заявок</small>
        </article>
      </section>

      <section className="panel booking-requests-panel" aria-labelledby="booking-requests-list-title">
        <header className="booking-requests-toolbar">
          <div>
            <h2 id="booking-requests-list-title">Вхідні заявки</h2>
            <p>{isLoading ? "Оновлюємо список…" : `Показано ${String(items.length)} із ${String(counts.total)}`}</p>
          </div>
          <div className="booking-requests-filters">
            <label className="booking-request-search">
              <span className="visually-hidden">Пошук заявок</span>
              <Icon name="search" />
              <input
                maxLength={100}
                onChange={(event) => { setSearch(event.target.value); }}
                placeholder="Ім’я, телефон, послуга, номер…"
                type="search"
                value={search}
              />
            </label>
            <label>
              <span className="visually-hidden">Статус заявок</span>
              <select
                aria-label="Статус заявок"
                onChange={(event) => { setStatus(event.target.value as BookingRequestStatus); }}
                value={status}
              >
                {statusOptions.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
            <label>
              <span className="visually-hidden">Джерело заявок</span>
              <select
                aria-label="Джерело заявок"
                onChange={(event) => { setSource(event.target.value as BookingRequestSource); }}
                value={source}
              >
                {sourceOptions.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
          </div>
        </header>

        {error !== null ? (
          <div className="booking-requests-error" role="alert">
            <Icon name="warning" />
            <span><strong>Не вдалося завантажити заявки</strong><small>{error}</small></span>
            <button className="button button--secondary" onClick={() => { void load(query); }} type="button">
              Повторити
            </button>
          </div>
        ) : null}

        {isLoading && items.length === 0 ? (
          <div aria-label="Завантаження заявок" className="booking-request-skeletons" role="status">
            <span /><span /><span /><span />
          </div>
        ) : null}

        {!isLoading && error === null && items.length === 0 ? (
          <div className="booking-requests-empty">
            <span><Icon name={search || status !== "NEW" || source !== "ALL" ? "search" : "inbox"} /></span>
            <h2>
              {search || status !== "NEW" || source !== "ALL"
                ? "Заявок за цими умовами немає"
                : "Нових заявок поки немає"}
            </h2>
            <p>
              {search || status !== "NEW" || source !== "ALL"
                ? "Змініть пошук або фільтри, щоб побачити інші звернення."
                : "Нові звернення з підключених каналів з’являться тут автоматично."}
            </p>
          </div>
        ) : null}

        {items.length > 0 ? (
          <>
            <div className="booking-request-table-wrap">
              <table className="booking-request-table">
                <thead>
                  <tr>
                    <th scope="col">Заявка</th>
                    <th scope="col">Клієнт</th>
                    <th scope="col">Джерело</th>
                    <th scope="col">Отримано</th>
                    <th scope="col">Статус</th>
                    <th scope="col"><span className="visually-hidden">Дії</span></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const created = formatShortDateTime(item.created_at);
                    return (
                      <tr key={item.id}>
                        <td><strong>{item.public_number}</strong></td>
                        <td>
                          <span className="booking-request-client">
                            <strong>{customerName(item)}</strong>
                            <small>{customerSummary(item)}</small>
                          </span>
                        </td>
                        <td><SourceBadge source={item.source} label={item.source_label} /></td>
                        <td><time dateTime={item.created_at}><strong>{created.time}</strong><span>{created.date}</span></time></td>
                        <td><RequestStatusBadge status={item.status} /></td>
                        <td>
                          <button
                            aria-label={`Відкрити заявку ${item.public_number} — ${customerName(item)}`}
                            className="booking-request-open"
                            onClick={() => { openDetail(item.id); }}
                            type="button"
                          >
                            <Icon name="chevron" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="booking-request-cards">
              {items.map((item) => (
                <button
                  aria-label={`Відкрити заявку ${item.public_number} — ${customerName(item)}`}
                  className="booking-request-card"
                  key={item.id}
                  onClick={() => { openDetail(item.id); }}
                  type="button"
                >
                  <span className="booking-request-card__top">
                    <strong>{item.public_number}</strong>
                    <RequestStatusBadge status={item.status} />
                  </span>
                  <span className="booking-request-card__client">
                    <strong>{customerName(item)}</strong>
                    <small>{customerSummary(item)}</small>
                  </span>
                  <span className="booking-request-card__footer">
                    <SourceBadge source={item.source} label={item.source_label} />
                    <time dateTime={item.created_at}>{formatDateTime(item.created_at)}</time>
                    <Icon name="chevron" />
                  </span>
                </button>
              ))}
            </div>
          </>
        ) : null}

        {nextCursor === null ? null : (
          <div className="booking-requests-load-more">
            <button
              className="button button--secondary"
              disabled={isLoadingMore}
              onClick={() => { void load(query, nextCursor); }}
              type="button"
            >
              {isLoadingMore ? "Завантажуємо…" : "Показати ще"}
            </button>
          </div>
        )}
      </section>

      {selectedRequestId === null ? null : (
        <BookingRequestDetail
          bookingRequestId={selectedRequestId}
          onClose={closeDetail}
          onProcessed={onProcessed}
        />
      )}
    </>
  );
}
