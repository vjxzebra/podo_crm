import { useCallback, useEffect, useState, type SyntheticEvent } from "react";

import { apiClient, sessionAwareFetch } from "../api/client";
import { attachmentFilename, downloadBlob, responseErrorMessage } from "../api/download";
import type { components, operations } from "../api/schema";
import { Icon } from "../app/Icon";

type Material = components["schemas"]["Material"];
type Movement = components["schemas"]["MovementJournalItem"];
type InventoryOperation = components["schemas"]["InventoryOperation"];
type JournalQuery = NonNullable<operations["inventory_movement_list"]["parameters"]["query"]>;
type MovementExportQuery = NonNullable<operations["inventory_movement_export"]["parameters"]["query"]>;
type MovementKind = Exclude<JournalQuery["kind"], undefined>;

const kindLabels: Readonly<Record<string, string>> = {
  RECEIPT: "Надходження",
  MANUAL_WRITEOFF: "Ручне списання",
  STOCKTAKE_ADJUSTMENT: "Інвентаризація",
};

function dateTimeLabel(value: string): string {
  return new Intl.DateTimeFormat("uk-UA", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function signedQuantity(value: string, unit: string): string {
  const amount = Number(value);
  return `${amount > 0 ? "+" : ""}${amount.toLocaleString("uk-UA", { maximumFractionDigits: 3 })} ${unit}`;
}

function exportUrl(query: JournalQuery): string {
  const url = new URL("/api/v1/inventory/movements/export", window.location.origin);
  const exportQuery: MovementExportQuery = {
    ...(query.search === undefined ? {} : { search: query.search }),
    ...(query.kind === undefined ? {} : { kind: query.kind }),
    ...(query.material_id === undefined ? {} : { material_id: query.material_id }),
    ...(query.actor === undefined ? {} : { actor: query.actor }),
    ...(query.date_from === undefined ? {} : { date_from: query.date_from }),
    ...(query.date_to === undefined ? {} : { date_to: query.date_to }),
  };
  Object.entries(exportQuery).forEach(([name, value]) => {
    url.searchParams.set(name, value);
  });
  return url.toString();
}

interface OperationDetailProps {
  readonly operation: InventoryOperation;
  readonly onClose: () => void;
}

function OperationDetail({ operation, onClose }: OperationDetailProps) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("keydown", closeOnEscape); };
  }, [onClose]);
  return <div className="modal-layer" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }} role="presentation"><section aria-labelledby="operation-detail-title" aria-modal="true" className="modal-card operation-detail" role="dialog"><header className="modal-card__header"><div><p className="eyebrow">Журнал · Незмінна операція</p><h2 id="operation-detail-title">{operation.public_number}</h2><p>{kindLabels[operation.kind] ?? operation.kind} · {dateTimeLabel(operation.posted_at)}</p></div><button aria-label="Закрити деталі операції" className="icon-button" onClick={onClose} type="button"><Icon name="close" /></button></header><div className="operation-detail__meta"><article><span>Провів(-ла)</span><strong>{operation.created_by_name}</strong><small>{operation.created_by_email}</small></article><article><span>Рухів</span><strong>{operation.movement_count}</strong><small>Append-only записи</small></article><article><span>Причина</span><strong>{operation.reason === "" ? "Не вказано" : operation.reason}</strong><small>{operation.comment === "" ? "Без коментаря" : operation.comment}</small></article></div><div className="operation-movements"><div className="operation-movements__head" aria-hidden="true"><span>Матеріал / партія</span><span>Зміна</span><span>Після операції</span></div>{operation.movements.map((movement) => <article key={movement.id}><span data-label="Матеріал"><strong>{movement.material_name}</strong><small>Партія №{movement.lot_number}</small></span><b className={Number(movement.quantity_delta) > 0 ? "movement-positive" : "movement-negative"} data-label="Зміна">{signedQuantity(movement.quantity_delta, movement.material_unit)}</b><span data-label="Після операції">{Number(movement.balance_after).toLocaleString("uk-UA", { maximumFractionDigits: 3 })} {movement.material_unit}</span></article>)}</div><footer className="modal-card__footer inventory-operation-footer"><span><Icon name="lock" />Операцію та рухи неможливо змінити або видалити.</span><div><button className="button button--primary" onClick={onClose} type="button">Готово</button></div></footer></section></div>;
}

interface MovementJournalProps {
  readonly materials: readonly Material[];
}

export function MovementJournal({ materials }: MovementJournalProps) {
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<MovementKind>("all");
  const [materialId, setMaterialId] = useState("");
  const [actor, setActor] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [query, setQuery] = useState<JournalQuery>({ kind: "all" });
  const [movements, setMovements] = useState<readonly Movement[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<InventoryOperation | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportStatus, setExportStatus] = useState<string | null>(null);

  const load = useCallback(async (currentQuery: JournalQuery, append = false) => {
    setIsLoading(true);
    setError(null);
    const result = await apiClient.GET("/api/v1/inventory/movements", {
      params: { query: currentQuery },
    }).catch(() => null);
    setIsLoading(false);
    if (result === null) {
      setError("Немає зв’язку із сервером. Не вдалося відкрити журнал.");
    } else if (result.data === undefined) {
      setError(result.error.message);
    } else {
      setMovements((current) => append ? [...current, ...result.data.movements] : result.data.movements);
      setNextCursor(result.data.next_cursor);
    }
  }, []);

  useEffect(() => { void load(query); }, [load, query]);

  const applyFilters = (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    setQuery({
      ...(search.trim() === "" ? {} : { search: search.trim() }),
      kind,
      ...(materialId === "" ? {} : { material_id: materialId }),
      ...(actor.trim() === "" ? {} : { actor: actor.trim() }),
      ...(dateFrom === "" ? {} : { date_from: dateFrom }),
      ...(dateTo === "" ? {} : { date_to: dateTo }),
    });
  };
  const resetFilters = () => {
    setSearch("");
    setKind("all");
    setMaterialId("");
    setActor("");
    setDateFrom("");
    setDateTo("");
    setQuery({ kind: "all" });
  };
  const openDetail = async (operationId: string) => {
    setIsLoadingDetail(true);
    setError(null);
    const result = await apiClient.GET("/api/v1/inventory/operations/{operation_id}", {
      params: { path: { operation_id: operationId } },
    }).catch(() => null);
    setIsLoadingDetail(false);
    if (result === null) setError("Немає зв’язку із сервером. Не вдалося відкрити операцію.");
    else if (result.data === undefined) setError(result.error.message);
    else setDetail(result.data);
  };
  const exportMovements = async () => {
    setIsExporting(true);
    setExportError(null);
    setExportStatus(null);
    const response = await sessionAwareFetch(new Request(exportUrl(query), {
      headers: { Accept: "text/csv" },
    })).catch(() => null);
    setIsExporting(false);
    if (response === null) {
      setExportError("Немає зв’язку із сервером. Не вдалося підготувати CSV.");
      return;
    }
    if (!response.ok) {
      setExportError(await responseErrorMessage(
        response,
        "Не вдалося підготувати CSV. Спробуйте ще раз.",
      ));
      return;
    }
    const blob = await response.blob();
    downloadBlob(blob, attachmentFilename(
      response.headers.get("Content-Disposition"),
      "inventory-movements.csv",
    ));
    setExportStatus("Завантаження CSV розпочато.");
  };
  const filtersActive = search !== "" || kind !== "all" || materialId !== ""
    || actor !== "" || dateFrom !== "" || dateTo !== "";

  return <>
    <section className="panel movement-journal"><header><div><p className="eyebrow">Append-only журнал · TP-1002</p><h2>Рухи матеріалів</h2><p>Надходження, списання та коригування інвентаризації в одному незмінному реєстрі.</p></div><div className="movement-journal__actions"><span className="admin-only-badge"><Icon name="lock" />Лише читання</span><button className="button button--secondary" disabled={isExporting} onClick={() => void exportMovements()} type="button">{isExporting ? "Готуємо CSV…" : "Експортувати CSV"}</button></div></header>{exportError === null ? null : <div className="form-message form-message--error movement-message" role="alert"><Icon name="warning" /><span>{exportError}</span><button className="text-action" onClick={() => void exportMovements()} type="button">Повторити export</button></div>}{exportStatus === null ? null : <div className="form-message form-message--success movement-message" role="status"><Icon name="check" /><span>{exportStatus}</span></div>}<form className="movement-filters" onSubmit={applyFilters}><label className="form-field movement-search"><span>Пошук</span><span className="input-with-icon"><Icon name="search" /><input onChange={(event) => { setSearch(event.target.value); }} placeholder="Операція, матеріал або партія" value={search} /></span></label><label className="form-field"><span>Тип руху</span><select onChange={(event) => { setKind(event.target.value as MovementKind); }} value={kind}><option value="all">Усі типи</option><option value="RECEIPT">Надходження</option><option value="MANUAL_WRITEOFF">Ручне списання</option><option value="STOCKTAKE_ADJUSTMENT">Інвентаризація</option></select></label><label className="form-field"><span>Матеріал</span><select onChange={(event) => { setMaterialId(event.target.value); }} value={materialId}><option value="">Усі матеріали</option>{materials.map((material) => <option key={material.id} value={material.id}>{material.sku} · {material.name}</option>)}</select></label><label className="form-field"><span>Працівник</span><input onChange={(event) => { setActor(event.target.value); }} placeholder="Ім’я або email" value={actor} /></label><label className="form-field"><span>Від дати</span><input max={dateTo || undefined} onChange={(event) => { setDateFrom(event.target.value); }} type="date" value={dateFrom} /></label><label className="form-field"><span>До дати</span><input min={dateFrom || undefined} onChange={(event) => { setDateTo(event.target.value); }} type="date" value={dateTo} /></label><div className="movement-filter-actions"><button aria-label="Скинути фільтри журналу" className="icon-button" disabled={!filtersActive} onClick={resetFilters} type="button"><Icon name="refresh" /></button><button className="button button--secondary" type="submit">Застосувати</button></div></form>
      {error === null ? null : <div className="form-message form-message--error movement-message" role="alert"><Icon name="warning" /><span>{error}</span><button className="text-action" onClick={() => void load(query)} type="button">Повторити</button></div>}
      {isLoading && movements.length === 0 ? <div className="inventory-empty" role="status"><span className="spinner" /><h3>Завантажуємо журнал…</h3></div> : null}
      {!isLoading && movements.length === 0 ? <div className="inventory-empty"><Icon name="empty" /><h3>Рухів не знайдено</h3><p>{filtersActive ? "Змініть критерії або скиньте фільтри." : "Проведені складські операції з’являться тут автоматично."}</p>{filtersActive ? <button className="button button--secondary" onClick={resetFilters} type="button">Скинути фільтри</button> : null}</div> : null}
      {movements.length > 0 ? <div className="movement-table"><div className="movement-table__head" aria-hidden="true"><span>Дата / операція</span><span>Тип</span><span>Матеріал / партія</span><span>Зміна</span><span>Після</span><span>Працівник</span><span /></div>{movements.map((movement) => <button aria-label={`Відкрити операцію ${movement.operation_public_number}`} className="movement-row" key={movement.id} onClick={() => void openDetail(movement.operation_id)} type="button"><span data-label="Операція"><strong>{dateTimeLabel(movement.posted_at)}</strong><small>{movement.operation_public_number}</small></span><span data-label="Тип"><b className={`movement-kind movement-kind--${movement.operation_kind.toLocaleLowerCase()}`}>{kindLabels[movement.operation_kind]}</b></span><span data-label="Матеріал"><strong>{movement.material_name}</strong><small>ART {movement.material_sku} · партія №{movement.lot_number}</small></span><b className={Number(movement.quantity_delta) > 0 ? "movement-positive" : "movement-negative"} data-label="Зміна">{signedQuantity(movement.quantity_delta, movement.material_unit)}</b><span data-label="Після">{Number(movement.balance_after).toLocaleString("uk-UA", { maximumFractionDigits: 3 })} {movement.material_unit}</span><span data-label="Працівник"><strong>{movement.actor_name}</strong><small>{movement.actor_email}</small></span><Icon name="chevron" /></button>)}</div> : null}
      {nextCursor === null ? null : <footer className="movement-journal__footer"><button className="button button--secondary" disabled={isLoading} onClick={() => void load({ ...query, cursor: nextCursor }, true)} type="button">{isLoading ? "Завантажуємо…" : "Показати наступні рухи"}</button></footer>}
    </section>
    {isLoadingDetail ? <div className="inventory-detail-loading" role="status"><span className="spinner" />Відкриваємо операцію…</div> : null}
    {detail === null ? null : <OperationDetail onClose={() => { setDetail(null); }} operation={detail} />}
  </>;
}
