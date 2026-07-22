import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { Link } from "react-router";

import { Icon, type IconName } from "../app/Icon";
import { useAuth } from "../auth/AuthContext";
import { searchGlobally } from "./globalSearchApi";
import type {
  GlobalSearchApiResult,
  GlobalSearchGroup,
  GlobalSearchGroupType,
  GlobalSearchItem,
} from "./searchTypes";
import { useModalLifecycle } from "../app/useModalLifecycle";

type SearchStatus = "idle" | "short" | "debouncing" | "loading" | "success" | "error";

interface SearchFailure {
  readonly message: string;
  readonly correlationId: string;
}

interface FlatResult {
  readonly group: GlobalSearchGroup;
  readonly item: GlobalSearchItem;
  readonly optionId: string;
}

const groupLabels: Readonly<Record<GlobalSearchGroupType, string>> = {
  patients: "Пацієнти",
  appointments: "Записи",
  payments: "Оплати",
  materials: "Матеріали",
};

const groupDescriptions: Readonly<Record<GlobalSearchGroupType, string>> = {
  patients: "Картки та безпечні контакти",
  appointments: "Доступні записи календаря",
  payments: "Дозволені фінансові операції",
  materials: "Каталог і залишки складу",
};

const groupIcons: Readonly<Record<GlobalSearchGroupType, IconName>> = {
  patients: "patients",
  appointments: "calendar",
  payments: "finance",
  materials: "inventory",
};

function resultCountLabel(value: number): string {
  const lastTwo = value % 100;
  const last = value % 10;
  if (last === 1 && lastTwo !== 11) return "результат";
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) return "результати";
  return "результатів";
}

function safeDeepLink(value: string): boolean {
  return value.startsWith("/") && !value.startsWith("//");
}

export function GlobalSearchOverlay({
  onClose,
  onNavigate,
  search = searchGlobally,
}: {
  readonly onClose: () => void;
  readonly onNavigate: () => void;
  readonly search?: (query: string, signal: AbortSignal) => Promise<GlobalSearchApiResult>;
}) {
  const { state } = useAuth();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<SearchStatus>("idle");
  const [groups, setGroups] = useState<readonly GlobalSearchGroup[]>([]);
  const [returnedCount, setReturnedCount] = useState(0);
  const [failure, setFailure] = useState<SearchFailure | null>(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [retryVersion, setRetryVersion] = useState(0);
  const dialogRef = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const resultRefs = useRef<(HTMLAnchorElement | null)[]>([]);
  const requestSequence = useRef(0);
  const normalizedQuery = query.trim();

  useModalLifecycle({ dialogRef, initialFocusRef: inputRef, onEscape: onClose });

  useEffect(() => {
    const sequence = requestSequence.current + 1;
    requestSequence.current = sequence;
    setFailure(null);
    setGroups([]);
    setReturnedCount(0);
    setActiveIndex(-1);

    if (normalizedQuery.length === 0) {
      setStatus("idle");
      return;
    }
    if (normalizedQuery.length < 2) {
      setStatus("short");
      return;
    }

    setStatus("debouncing");
    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      setStatus("loading");
      void search(normalizedQuery, controller.signal).then((result) => {
        if (sequence !== requestSequence.current || controller.signal.aborted) return;
        if (!result.ok) {
          setFailure({
            message: result.error.message,
            correlationId: result.error.correlation_id,
          });
          setStatus("error");
          return;
        }
        setGroups(result.data.groups);
        setReturnedCount(result.data.returned_count);
        const firstResultExists = result.data.groups.some((group) => group.items.length > 0);
        setActiveIndex(firstResultExists ? 0 : -1);
        setStatus("success");
      }).catch((reason: unknown) => {
        if (sequence !== requestSequence.current || controller.signal.aborted) return;
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        const offline = typeof navigator !== "undefined" && !navigator.onLine;
        setFailure({
          message: offline
            ? "Немає з’єднання з мережею. Відновіть його та повторіть пошук."
            : "Немає зв’язку із сервером. Спробуйте ще раз.",
          correlationId: "",
        });
        setStatus("error");
      });
    }, 250);

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [normalizedQuery, retryVersion, search]);

  const flatResults = useMemo<readonly FlatResult[]>(() => groups.flatMap((group, groupIndex) =>
    group.items
      .filter((item) => safeDeepLink(item.deep_link))
      .map((item, itemIndex) => ({
        group,
        item,
        optionId: `global-search-option-${String(groupIndex)}-${String(itemIndex)}`,
      }))), [groups]);

  useEffect(() => {
    resultRefs.current.length = flatResults.length;
    if (flatResults.length === 0) setActiveIndex(-1);
    else if (activeIndex >= flatResults.length) setActiveIndex(0);
  }, [activeIndex, flatResults.length]);

  const moveActive = (nextIndex: number) => {
    if (flatResults.length === 0) return;
    const normalized = (nextIndex + flatResults.length) % flatResults.length;
    setActiveIndex(normalized);
    resultRefs.current[normalized]?.scrollIntoView({ block: "nearest" });
  };

  const onSearchKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      moveActive(activeIndex < 0 ? 0 : activeIndex + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      moveActive(activeIndex < 0 ? flatResults.length - 1 : activeIndex - 1);
    } else if (event.key === "Home" && flatResults.length > 0) {
      event.preventDefault();
      moveActive(0);
    } else if (event.key === "End" && flatResults.length > 0) {
      event.preventDefault();
      moveActive(flatResults.length - 1);
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      resultRefs.current[activeIndex]?.click();
    }
  };

  const routeIds = state.status === "authenticated" ? state.session.route_ids : [];
  const canCreatePatient = routeIds.includes("patients");
  const canCreateAppointment = routeIds.includes("calendar");
  const activeOptionId = activeIndex >= 0 ? flatResults[activeIndex]?.optionId : undefined;
  const settledEmpty = status === "success" && flatResults.length === 0;

  return (
    <div
      className="global-search-overlay"
      onMouseDown={(event) => {
        if (event.currentTarget === event.target) onClose();
      }}
      role="presentation"
    >
      <section
        aria-labelledby="global-search-title"
        aria-modal="true"
        className="global-search-dialog"
        id="global-search-dialog"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <div className="global-search-dialog__header">
          <div className="global-search-dialog__heading">
            <span aria-hidden="true"><Icon name="search" /></span>
            <div><h2 id="global-search-title">Глобальний пошук</h2><p>Доступні лише об’єкти в межах вашої ролі.</p></div>
          </div>
          <button aria-label="Закрити глобальний пошук" className="icon-button" onClick={onClose} type="button"><Icon name="close" /></button>
        </div>

        <label className="global-search-dialog__input">
          <span className="visually-hidden">Пошуковий запит</span>
          <Icon name="search" />
          <input
            aria-activedescendant={activeOptionId}
            aria-autocomplete="list"
            aria-controls="global-search-results"
            aria-expanded="true"
            autoComplete="off"
            maxLength={100}
            onChange={(event) => { setQuery(event.target.value); }}
            onKeyDown={onSearchKeyDown}
            placeholder="Ім’я, телефон, номер, код або артикул"
            ref={inputRef}
            role="combobox"
            spellCheck={false}
            type="search"
            value={query}
          />
          <kbd aria-hidden="true">Esc</kbd>
        </label>

        <p aria-live="polite" className="visually-hidden" role="status">
          {status === "loading" ? "Виконуємо пошук." : status === "success" ? `Знайдено ${String(returnedCount)} ${resultCountLabel(returnedCount)}.` : ""}
        </p>

        <div aria-busy={status === "debouncing" || status === "loading"} className="global-search-dialog__results" id="global-search-results" role={flatResults.length > 0 ? "listbox" : undefined}>
          {status === "idle" ? <div className="global-search-state"><Icon name="search" /><h3>Почніть вводити запит</h3><p>Щонайменше два символи: ім’я, телефон, номер, код або артикул.</p></div> : null}
          {status === "short" ? <div className="global-search-state"><Icon name="search" /><h3>Потрібно ще один символ</h3><p>Пошук почнеться автоматично.</p></div> : null}
          {status === "debouncing" ? <div className="global-search-state global-search-state--loading" role="status"><span className="spinner" /><p>Готуємо пошук…</p></div> : null}
          {status === "loading" ? <div aria-label="Завантаження результатів глобального пошуку" className="global-search-loading" role="status"><span /><span /><span /></div> : null}
          {status === "error" && failure !== null ? (
            <div className="global-search-state global-search-state--error" role="alert">
              <Icon name="warning" /><h3>Не вдалося виконати пошук</h3><p>{failure.message}</p>
              {failure.correlationId === "" ? null : <small>Код запиту: {failure.correlationId}</small>}
              <button className="button button--secondary" onClick={() => { setRetryVersion((current) => current + 1); }} type="button"><Icon name="refresh" />Повторити</button>
            </div>
          ) : null}
          {settledEmpty ? <div className="global-search-state"><Icon name="empty" /><h3>Нічого не знайдено</h3><p>Перевірте запит або створіть нову картку чи запис.</p></div> : null}

          {status === "success" ? groups.map((group, groupIndex) => {
            const groupItems = flatResults.filter((result) => result.group === group);
            if (groupItems.length === 0) return null;
            const headingId = `global-search-group-${String(groupIndex)}`;
            return (
              <section aria-label={groupLabels[group.type]} className="global-search-group" key={group.type} role="group">
                <div aria-hidden="true" className="global-search-group__header"><div><h3 id={headingId}>{groupLabels[group.type]}</h3><p>{groupDescriptions[group.type]}</p></div>{group.has_more ? <small>Є ще — уточніть запит</small> : null}</div>
                {groupItems.map(({ item, optionId }) => {
                  const flatIndex = flatResults.findIndex((result) => result.optionId === optionId);
                  return (
                    <Link
                      aria-selected={flatIndex === activeIndex}
                      className={flatIndex === activeIndex ? "global-search-result global-search-result--active" : "global-search-result"}
                      id={optionId}
                      key={`${item.type}:${item.id}`}
                      onClick={onNavigate}
                      onMouseEnter={() => { setActiveIndex(flatIndex); }}
                      ref={(element) => { resultRefs.current[flatIndex] = element; }}
                      role="option"
                      tabIndex={-1}
                      to={item.deep_link}
                    >
                      <span className={`global-search-result__icon global-search-result__icon--${group.type}`} aria-hidden="true"><Icon name={groupIcons[group.type]} /></span>
                      <span className="global-search-result__copy"><strong>{item.title}</strong><small>{item.subtitle}</small>{item.meta === "" ? null : <small>{item.meta}</small>}</span>
                      <span className="global-search-result__category">{groupLabels[group.type]}</span>
                      <Icon name="chevron" />
                    </Link>
                  );
                })}
              </section>
            );
          }) : null}
        </div>

        <footer className="global-search-dialog__footer">
          <span><kbd>↑</kbd><kbd>↓</kbd> навігація · <kbd>Enter</kbd> відкрити</span>
          <div>
            {canCreatePatient ? <Link className="button button--secondary" onClick={onNavigate} to="/patients?compose=patient"><Icon name="plus" />Новий пацієнт</Link> : null}
            {canCreateAppointment ? <Link className="button button--primary" onClick={onNavigate} to="/calendar?compose=appointment"><Icon name="plus" />Новий запис</Link> : null}
          </div>
        </footer>
      </section>
    </div>
  );
}
