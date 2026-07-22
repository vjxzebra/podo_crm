import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type SyntheticEvent,
} from "react";
import { useLocation, useSearchParams } from "react-router";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { useAuth } from "../auth/AuthContext";
import { getCashShift, listCashShifts } from "./cashShiftApi";
import { CashShiftDetailDialog } from "./CashShiftDetailDialog";
import type {
  CashShiftCloseResponse,
  CashShiftListQuery,
  CashShiftProjection,
  CashShiftStatus,
  CashShiftSummary,
} from "./cashShiftTypes";
import { CloseCashShiftDialog } from "./CloseCashShiftDialog";
import { dateTimeFormatter, money } from "./financeFormat";
import { FinanceSubnav } from "./FinanceSubnav";

type TeamUser = components["schemas"]["TeamUser"];
type PeriodMode = "all" | "day" | "month" | "custom";
type StatusFilter = "all" | CashShiftStatus;

function kyivDateParts(now = new Date()): { readonly year: number; readonly month: number; readonly day: number } {
  const values = Object.fromEntries(
    new Intl.DateTimeFormat("en", {
      timeZone: "Europe/Kyiv",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(now).map((part) => [part.type, part.value]),
  );
  return {
    year: Number(values.year),
    month: Number(values.month),
    day: Number(values.day),
  };
}

function isoDate(year: number, month: number, day: number): string {
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function presetDates(mode: PeriodMode): { readonly from: string; readonly to: string } {
  if (mode === "all" || mode === "custom") return { from: "", to: "" };
  const { year, month, day } = kyivDateParts();
  if (mode === "day") {
    const today = isoDate(year, month, day);
    return { from: today, to: today };
  }
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return { from: isoDate(year, month, 1), to: isoDate(year, month, lastDay) };
}

function useMobileHistoryLayout(): boolean {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth <= 720);
  useEffect(() => {
    const update = () => { setIsMobile(window.innerWidth <= 720); };
    update();
    window.addEventListener("resize", update);
    return () => { window.removeEventListener("resize", update); };
  }, []);
  return isMobile;
}

function discrepancy(summary: CashShiftSummary): string {
  const value = summary.reconciliation?.discrepancy_minor;
  if (value === undefined) return "—";
  return `${value > 0 ? "+" : value < 0 ? "−" : ""}${money(Math.abs(value))}`;
}

interface HistoryRowsProps {
  readonly isMobile: boolean;
  readonly onOpen: (shift: CashShiftSummary, trigger: HTMLButtonElement) => void;
  readonly shifts: readonly CashShiftSummary[];
}

function HistoryRows({ isMobile, onOpen, shifts }: HistoryRowsProps) {
  if (isMobile) {
    return (
      <ul aria-label="Історія касових змін" className="finance-history-cards">
        {shifts.map((shift) => (
          <li className="finance-history-card" key={shift.id}>
            <header><div><strong>{shift.public_number}</strong><time dateTime={shift.opened_at}>{dateTimeFormatter.format(new Date(shift.opened_at))}</time></div><span className={`finance-history-status finance-history-status--${shift.status.toLocaleLowerCase()}`}>{shift.status === "CLOSED" ? "Закрита" : "Відкрита"}</span></header>
            <p><span className="avatar" aria-hidden="true">{shift.employee.name.slice(0, 1).toLocaleUpperCase("uk")}</span><span><strong>{shift.employee.name}</strong><small>{shift.employee.email}</small></span></p>
            <dl><div><dt>Відкрито / закрито</dt><dd>{new Intl.DateTimeFormat("uk-UA", { timeZone: "Europe/Kyiv", hour: "2-digit", minute: "2-digit" }).format(new Date(shift.opened_at))} / {shift.closed_at === null ? "—" : new Intl.DateTimeFormat("uk-UA", { timeZone: "Europe/Kyiv", hour: "2-digit", minute: "2-digit" }).format(new Date(shift.closed_at))}</dd></div><div><dt>Виторг</dt><dd>{money(shift.totals.revenue_minor)}</dd></div><div><dt>Готівка / картка</dt><dd>{money(shift.totals.cash_payments_minor - shift.totals.cash_refunds_minor)} / {money(shift.totals.card_payments_minor - shift.totals.card_refunds_minor)}</dd></div><div><dt>Очік. / факт.</dt><dd>{money(shift.totals.expected_cash_minor)} / {shift.reconciliation === null ? "—" : money(shift.reconciliation.actual_cash_minor)}</dd></div><div><dt>Розбіжність</dt><dd>{discrepancy(shift)}</dd></div></dl>
            <button className="button button--secondary button--full" onClick={(event) => { onOpen(shift, event.currentTarget); }} type="button">Деталі зміни</button>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <>
    <p className="finance-history-table__scroll-hint" id="finance-history-scroll-hint"><Icon name="chevron" />Прокрутіть таблицю горизонтально, щоб переглянути всі стовпці.</p>
    <div aria-describedby="finance-history-scroll-hint" aria-label="Історія касових змін" className="finance-history-table" role="table" tabIndex={0}>
      <div className="finance-history-table__head" role="row"><span role="columnheader">Дата / зміна</span><span role="columnheader">Працівник</span><span role="columnheader">Час роботи</span><span role="columnheader">Виторг</span><span role="columnheader">Готівка</span><span role="columnheader">Картка</span><span role="columnheader">Очік. / факт.</span><span role="columnheader">Розбіжність</span><span role="columnheader">Статус</span><span role="columnheader">Дії</span></div>
      {shifts.map((shift) => (
        <div className="finance-history-table__row" key={shift.id} role="row">
          <span role="cell"><strong>{dateTimeFormatter.format(new Date(shift.opened_at))}</strong><small>{shift.public_number}</small></span>
          <span role="cell"><strong>{shift.employee.name}</strong><small>{shift.employee.email}</small></span>
          <span role="cell"><strong>{new Intl.DateTimeFormat("uk-UA", { timeZone: "Europe/Kyiv", hour: "2-digit", minute: "2-digit" }).format(new Date(shift.opened_at))}</strong><small>{shift.closed_at === null ? "Ще відкрита" : `до ${new Intl.DateTimeFormat("uk-UA", { timeZone: "Europe/Kyiv", hour: "2-digit", minute: "2-digit" }).format(new Date(shift.closed_at))}`}</small></span>
          <span className="finance-history-money" role="cell">{money(shift.totals.revenue_minor)}</span>
          <span className="finance-history-money" role="cell">{money(shift.totals.cash_payments_minor - shift.totals.cash_refunds_minor)}</span>
          <span className="finance-history-money" role="cell">{money(shift.totals.card_payments_minor - shift.totals.card_refunds_minor)}</span>
          <span role="cell"><strong>{money(shift.totals.expected_cash_minor)}</strong><small>{shift.reconciliation === null ? "—" : money(shift.reconciliation.actual_cash_minor)}</small></span>
          <span className={shift.reconciliation !== null && shift.reconciliation.discrepancy_minor !== 0 ? "finance-history-discrepancy" : undefined} role="cell">{discrepancy(shift)}</span>
          <span role="cell"><b className={`finance-history-status finance-history-status--${shift.status.toLocaleLowerCase()}`}>{shift.status === "CLOSED" ? "Закрита" : "Відкрита"}</b></span>
          <span role="cell"><button aria-label={`Відкрити деталі ${shift.public_number}`} className="icon-button" onClick={(event) => { onOpen(shift, event.currentTarget); }} type="button"><Icon name="chevron" /></button></span>
        </div>
      ))}
    </div>
    </>
  );
}

export function CashShiftHistoryPage() {
  const { state: authState } = useAuth();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const isAdmin = authState.status === "authenticated" && authState.session.user.role === "admin";
  const isMobile = useMobileHistoryLayout();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [period, setPeriod] = useState<PeriodMode>("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [employees, setEmployees] = useState<readonly TeamUser[]>([]);
  const [query, setQuery] = useState<CashShiftListQuery>({});
  const [shifts, setShifts] = useState<readonly CashShiftSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [attemptedDetailId, setAttemptedDetailId] = useState<string | null>(null);
  const [filterError, setFilterError] = useState<string | null>(null);
  const [detail, setDetail] = useState<CashShiftProjection | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [closingShift, setClosingShift] = useState<CashShiftProjection | null>(null);
  const [flash, setFlash] = useState<string | null>(() => {
    const routeState = location.state as { readonly financeFlash?: unknown } | null;
    return typeof routeState?.financeFlash === "string" ? routeState.financeFlash : null;
  });
  const requestSequence = useRef(0);
  const detailRequestSequence = useRef(0);
  const detailTriggerRef = useRef<HTMLButtonElement | null>(null);
  const autoOpenedShiftRef = useRef<string | null>(null);

  const load = useCallback(async (nextQuery: CashShiftListQuery, append = false) => {
    const sequence = requestSequence.current + 1;
    requestSequence.current = sequence;
    setIsLoading(true);
    setError(null);
    if (!append) {
      setShifts([]);
      setNextCursor(null);
    }
    const response = await listCashShifts(nextQuery).catch(() => null);
    if (sequence !== requestSequence.current) return;
    setIsLoading(false);
    if (response === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
      return;
    }
    if (!response.ok) {
      setError(response.error.message);
      return;
    }
    setShifts((current) => append ? [...current, ...response.data.shifts] : response.data.shifts);
    setNextCursor(response.data.next_cursor);
  }, []);

  useEffect(() => { void load(query); }, [load, query]);

  useEffect(() => {
    if (!isAdmin) return;
    void apiClient.GET("/api/v1/users").then(({ data }) => {
      if (data !== undefined) setEmployees(data.users);
    }).catch(() => undefined);
  }, [isAdmin]);

  const closeDetail = useCallback(() => {
    setDetail(null);
    setAttemptedDetailId(null);
    const next = new URLSearchParams(searchParams);
    next.delete("shift");
    setSearchParams(next, { replace: true });
    window.setTimeout(() => { detailTriggerRef.current?.focus(); }, 0);
  }, [searchParams, setSearchParams]);

  const loadDetail = useCallback(async (shiftId: string) => {
    const sequence = detailRequestSequence.current + 1;
    detailRequestSequence.current = sequence;
    setIsDetailLoading(true);
    setDetailError(null);
    setAttemptedDetailId(shiftId);
    const response = await getCashShift(shiftId).catch(() => null);
    if (sequence !== detailRequestSequence.current) return;
    setIsDetailLoading(false);
    if (response === null) {
      setDetailError("Немає зв’язку із сервером. Не вдалося відкрити зміну.");
      return;
    }
    if (!response.ok) {
      setDetailError(response.error.message);
      return;
    }
    setDetail(response.data);
    const next = new URLSearchParams(searchParams);
    next.set("shift", shiftId);
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  const requestedShiftId = searchParams.get("shift");
  useEffect(() => {
    if (requestedShiftId === null || autoOpenedShiftRef.current === requestedShiftId) return;
    autoOpenedShiftRef.current = requestedShiftId;
    void loadDetail(requestedShiftId);
  }, [loadDetail, requestedShiftId]);

  const applyFilters = (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (dateFrom !== "" && dateTo !== "" && dateFrom > dateTo) {
      setFilterError("Дата «Від» не може бути пізнішою за дату «До».");
      return;
    }
    setFilterError(null);
    setQuery({
      ...(search.trim() === "" ? {} : { search: search.trim() }),
      ...(status === "all" ? {} : { status }),
      ...(dateFrom === "" ? {} : { date_from: dateFrom }),
      ...(dateTo === "" ? {} : { date_to: dateTo }),
      ...(!isAdmin || employeeId === "" ? {} : { employee_id: Number(employeeId) }),
    });
  };

  const resetFilters = () => {
    setSearch("");
    setStatus("all");
    setPeriod("all");
    setDateFrom("");
    setDateTo("");
    setEmployeeId("");
    setFilterError(null);
    setQuery({});
  };

  const filtersActive = useMemo(() => Object.keys(query).length > 0, [query]);
  const openRow = (shift: CashShiftSummary, trigger: HTMLButtonElement) => {
    detailTriggerRef.current = trigger;
    autoOpenedShiftRef.current = shift.id;
    void loadDetail(shift.id);
  };

  const closeSucceeded = async (result: CashShiftCloseResponse) => {
    setClosingShift(null);
    setDetail(result.shift);
    setFlash(result.replayed ? `Зміну ${result.shift.public_number} вже було закрито.` : `Касову зміну ${result.shift.public_number} закрито.`);
    await load(query);
  };

  return (
    <>
      <header className="page-heading finance-heading">
        <div><p className="eyebrow">Фінанси · TP-704</p><h1>Історія касових змін</h1><p>{isAdmin ? "Усі зміни клініки з незмінними підсумками та звіркою." : "Ваші касові зміни з повним журналом операцій і звіркою."}</p></div>
      </header>
      <FinanceSubnav />

      {flash === null ? null : <div className="success-banner finance-success" role="status"><Icon name="check" /><span>{flash}</span><button aria-label="Закрити повідомлення" className="icon-button" onClick={() => { setFlash(null); }} type="button"><Icon name="close" /></button></div>}

      <section aria-labelledby="finance-history-title" className="panel finance-history">
        <header className="finance-history__header"><div><p className="eyebrow">Каса · Immutable history</p><h2 id="finance-history-title">Касові зміни</h2><p>{shifts.length} завантажено · {isAdmin ? "усі працівники" : "лише ваші зміни"}</p></div><span><Icon name="lock" />Лише читання</span></header>

        <form className="finance-history-filters" onSubmit={applyFilters}>
          <label className="form-field finance-history-search"><span>Пошук</span><span className="input-with-icon"><Icon name="search" /><input maxLength={255} onChange={(event) => { setSearch(event.target.value); }} placeholder="Номер зміни або працівник" value={search} /></span></label>
          <label className="form-field"><span>Період</span><select aria-label="Період історії" onChange={(event) => {
            const nextPeriod = event.target.value as PeriodMode;
            setPeriod(nextPeriod);
            if (nextPeriod !== "custom") {
              const dates = presetDates(nextPeriod);
              setDateFrom(dates.from);
              setDateTo(dates.to);
            }
            setFilterError(null);
          }} value={period}><option value="all">Увесь час</option><option value="day">Сьогодні</option><option value="month">Цей місяць</option><option value="custom">Власний період</option></select></label>
          <label className="form-field"><span>Від дати</span><input disabled={period !== "custom"} onChange={(event) => { setDateFrom(event.target.value); setFilterError(null); }} type="date" value={dateFrom} /></label>
          <label className="form-field"><span>До дати</span><input disabled={period !== "custom"} onChange={(event) => { setDateTo(event.target.value); setFilterError(null); }} type="date" value={dateTo} /></label>
          <label className="form-field"><span>Статус</span><select aria-label="Статус касової зміни" onChange={(event) => { setStatus(event.target.value as StatusFilter); }} value={status}><option value="all">Усі статуси</option><option value="OPEN">Відкрита</option><option value="CLOSED">Закрита</option></select></label>
          {isAdmin ? <label className="form-field"><span>Працівник</span><select aria-label="Працівник касової зміни" onChange={(event) => { setEmployeeId(event.target.value); }} value={employeeId}><option value="">Усі працівники</option>{employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.display_name}</option>)}</select></label> : null}
          <div className="finance-history-filter-actions"><button aria-label="Скинути фільтри касових змін" className="icon-button" disabled={!filtersActive && search === "" && status === "all" && period === "all" && employeeId === ""} onClick={resetFilters} type="button"><Icon name="refresh" /></button><button className="button button--secondary" type="submit">Застосувати</button></div>
        </form>

        {filterError === null ? null : <div className="form-message form-message--error finance-history-message" role="alert"><Icon name="warning" /><span>{filterError}</span></div>}
        {error === null ? null : <div className="form-message form-message--error finance-history-message" role="alert"><Icon name="warning" /><span>{error}</span><button className="text-action" onClick={() => { void load(query); }} type="button">Повторити</button></div>}
        {detailError === null ? null : <div className="form-message form-message--error finance-history-message" role="alert"><Icon name="warning" /><span>{detailError}</span>{attemptedDetailId === null ? null : <button className="text-action" onClick={() => { void loadDetail(attemptedDetailId); }} type="button">Повторити деталі</button>}</div>}
        {isDetailLoading ? <div aria-label="Завантаження деталей касової зміни" className="finance-history-detail-loading" role="status"><span className="spinner" />Завантажуємо деталі…</div> : null}
        {isLoading && shifts.length === 0 ? <div aria-label="Завантаження історії касових змін" className="finance-history-loading" role="status"><span className="spinner" /><p>Завантажуємо касові зміни…</p></div> : null}
        {!isLoading && error === null && shifts.length === 0 ? <div className="finance-history-empty"><Icon name="empty" /><h3>{filtersActive ? "Змін за фільтрами не знайдено" : "Касових змін ще немає"}</h3><p>{filtersActive ? "Змініть критерії або скиньте фільтри." : "Після відкриття каси зміна з’явиться в цій історії."}</p>{filtersActive ? <button className="button button--secondary" onClick={resetFilters} type="button">Скинути фільтри</button> : null}</div> : null}
        {shifts.length > 0 ? <HistoryRows isMobile={isMobile} onOpen={openRow} shifts={shifts} /> : null}
        {nextCursor === null ? null : <footer className="finance-history-load-more"><button className="button button--secondary" disabled={isLoading} onClick={() => { void load({ ...query, cursor: nextCursor }, true); }} type="button">{isLoading ? "Завантажуємо…" : "Показати ще"}</button></footer>}
      </section>

      {detail === null ? null : <CashShiftDetailDialog onClose={closeDetail} {...(detail.status === "OPEN" ? { onRequestClose: () => { setClosingShift(detail); setDetail(null); } } : {})} shift={detail} />}
      {closingShift === null ? null : <CloseCashShiftDialog onClose={() => { setDetail(closingShift); setClosingShift(null); }} onSuccess={closeSucceeded} shiftId={closingShift.id} shiftNumber={closingShift.public_number} />}
    </>
  );
}
