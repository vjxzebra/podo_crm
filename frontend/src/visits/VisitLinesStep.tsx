import { useEffect, useMemo, useState } from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";

export type VisitServiceLine = components["schemas"]["VisitServiceLine"];
export type VisitMaterialLine = components["schemas"]["VisitMaterialLine"];
type ServiceOption = components["schemas"]["Service"];
type MaterialOption = components["schemas"]["VisitMaterialOption"];

type LoadState = "idle" | "loading" | "ready" | "error";

type VisitLinesStepProps = Readonly<{
  visitId: string;
  serviceLines: readonly VisitServiceLine[];
  materialLines: readonly VisitMaterialLine[];
  disabled: boolean;
  fieldError: string | null;
  onServiceLinesChange: (lines: readonly VisitServiceLine[]) => void;
  onMaterialLinesChange: (lines: readonly VisitMaterialLine[]) => void;
}>;

const moneyFormatter = new Intl.NumberFormat("uk-UA", {
  style: "currency",
  currency: "UAH",
  minimumFractionDigits: 2,
});

const dateFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: "Europe/Kyiv",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

function money(minor: number): string {
  return moneyFormatter.format(minor / 100);
}

function decimal(value: string): number {
  const parsed = Number(value.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : 0;
}

export function linesAreValid(
  serviceLines: readonly VisitServiceLine[],
  materialLines: readonly VisitMaterialLine[],
): boolean {
  return serviceLines.every((line) => Number.isInteger(line.quantity)
      && line.quantity >= 1
      && line.quantity <= 99)
    && materialLines.every((line) => {
      const quantity = decimal(line.quantity);
      return line.is_available
        && quantity > 0
        && quantity <= decimal(line.available_quantity);
    });
}

function syntheticId(prefix: string, sourceId: string): string {
  return `${prefix}-${sourceId}`;
}

export function VisitLinesStep({
  visitId,
  serviceLines,
  materialLines,
  disabled,
  fieldError,
  onServiceLinesChange,
  onMaterialLinesChange,
}: VisitLinesStepProps) {
  const [serviceSearch, setServiceSearch] = useState("");
  const [serviceOptions, setServiceOptions] = useState<readonly ServiceOption[]>([]);
  const [serviceState, setServiceState] = useState<LoadState>("idle");
  const [serviceError, setServiceError] = useState<string | null>(null);
  const [materialDialogOpen, setMaterialDialogOpen] = useState(false);
  const [materialSearch, setMaterialSearch] = useState("");
  const [materialOptions, setMaterialOptions] = useState<readonly MaterialOption[]>([]);
  const [materialState, setMaterialState] = useState<LoadState>("idle");
  const [materialError, setMaterialError] = useState<string | null>(null);
  const [selectedMaterial, setSelectedMaterial] = useState<MaterialOption | null>(null);
  const [selectedLotId, setSelectedLotId] = useState("");
  const [materialQuantity, setMaterialQuantity] = useState("1.000");

  useEffect(() => {
    let current = true;
    setServiceState("loading");
    setServiceError(null);
    const timeout = window.setTimeout(() => {
      void apiClient.GET("/api/v1/services", {
        params: { query: { search: serviceSearch, status: "active" } },
      }).then((result) => {
        if (!current) return;
        if (result.data === undefined) {
          setServiceState("error");
          setServiceError(result.error.message);
          return;
        }
        setServiceOptions(result.data.services);
        setServiceState("ready");
      }).catch(() => {
        if (!current) return;
        setServiceState("error");
        setServiceError("Не вдалося завантажити послуги. Повторіть пошук.");
      });
    }, 250);
    return () => {
      current = false;
      window.clearTimeout(timeout);
    };
  }, [serviceSearch]);

  useEffect(() => {
    if (!materialDialogOpen) return;
    let current = true;
    setMaterialState("loading");
    setMaterialError(null);
    const timeout = window.setTimeout(() => {
      void apiClient.GET("/api/v1/visits/{visit_id}/material-options", {
        params: { path: { visit_id: visitId }, query: { search: materialSearch } },
      }).then((result) => {
        if (!current) return;
        if (result.data === undefined) {
          setMaterialState("error");
          setMaterialError(result.error.message);
          return;
        }
        setMaterialOptions(result.data.materials);
        setMaterialState("ready");
      }).catch(() => {
        if (!current) return;
        setMaterialState("error");
        setMaterialError("Не вдалося завантажити матеріали. Повторіть пошук.");
      });
    }, 250);
    return () => {
      current = false;
      window.clearTimeout(timeout);
    };
  }, [materialDialogOpen, materialSearch, visitId]);

  const servicesTotal = useMemo(
    () => serviceLines.reduce((total, line) => total + line.price_minor * line.quantity, 0),
    [serviceLines],
  );
  const selectedLot = selectedMaterial?.lots.find((lot) => lot.id === selectedLotId) ?? null;
  const selectedQuantity = decimal(materialQuantity);
  const materialQuantityValid = selectedLot !== null
    && selectedQuantity > 0
    && selectedQuantity <= decimal(selectedLot.current_quantity);

  const addService = (service: ServiceOption) => {
    const existing = serviceLines.find((line) => line.service_id === service.id);
    if (existing !== undefined) {
      onServiceLinesChange(serviceLines.map((line) => line.service_id === service.id
        ? {
            ...line,
            quantity: Math.min(99, line.quantity + 1),
            line_total_minor: line.price_minor * Math.min(99, line.quantity + 1),
          }
        : line));
      return;
    }
    onServiceLinesChange([...serviceLines, {
      id: syntheticId("service", service.id),
      service_id: service.id,
      service_code: service.code,
      service_name: service.name,
      duration_minutes: service.duration_minutes,
      price_minor: service.price_minor,
      quantity: 1,
      is_primary: false,
      line_total_minor: service.price_minor,
    }]);
  };

  const updateServiceQuantity = (serviceId: string, quantity: number) => {
    onServiceLinesChange(serviceLines.map((line) => line.service_id === serviceId
      ? { ...line, quantity, line_total_minor: line.price_minor * quantity }
      : line));
  };

  const chooseMaterial = (material: MaterialOption) => {
    const lot = material.lots[0];
    setSelectedMaterial(material);
    setSelectedLotId(lot?.id ?? "");
    setMaterialQuantity(lot === undefined
      ? ""
      : Math.min(1, decimal(lot.current_quantity)).toFixed(3));
    setMaterialError(null);
  };

  const closeMaterialDialog = () => {
    setMaterialDialogOpen(false);
    setSelectedMaterial(null);
    setSelectedLotId("");
    setMaterialQuantity("1.000");
    setMaterialError(null);
  };

  const addMaterial = () => {
    if (selectedMaterial === null || selectedLot === null || !materialQuantityValid) {
      setMaterialError("Укажіть додатну кількість у межах доступного залишку партії.");
      return;
    }
    const existing = materialLines.find((line) => line.lot_id === selectedLot.id);
    if (existing !== undefined) {
      const combined = decimal(existing.quantity) + selectedQuantity;
      if (combined > decimal(selectedLot.current_quantity)) {
        setMaterialError(`У партії доступно ${selectedLot.current_quantity} ${selectedMaterial.unit}.`);
        return;
      }
      onMaterialLinesChange(materialLines.map((line) => line.lot_id === selectedLot.id
        ? { ...line, quantity: combined.toFixed(3) }
        : line));
    } else {
      onMaterialLinesChange([...materialLines, {
        id: syntheticId("material", selectedLot.id),
        material_id: selectedMaterial.id,
        lot_id: selectedLot.id,
        material_sku: selectedMaterial.sku,
        material_name: selectedMaterial.name,
        material_unit: selectedMaterial.unit,
        lot_number: selectedLot.lot_number,
        expires_on: selectedLot.expires_on,
        quantity: selectedQuantity.toFixed(3),
        available_quantity: selectedLot.current_quantity,
        is_available: true,
      }]);
    }
    closeMaterialDialog();
  };

  return (
    <>
      <div className="visit-lines-grid">
        <section className="visit-lines-section" aria-labelledby="visit-services-title">
          <header>
            <div>
              <p className="eyebrow">Послуги</p>
              <h3 id="visit-services-title">Виконані послуги</h3>
              <p>Основну послугу підставлено із запису. Повторне додавання збільшує кількість.</p>
            </div>
            <strong className="visit-lines-total">{money(servicesTotal)}</strong>
          </header>

          <label className="form-field visit-line-search">
            <span>Пошук послуги за назвою або кодом</span>
            <input
              disabled={disabled}
              onChange={(event) => { setServiceSearch(event.target.value); }}
              placeholder="Наприклад, консультація або CONSULT"
              type="search"
              value={serviceSearch}
            />
          </label>
          <div className="visit-option-results" aria-live="polite">
            {serviceState === "loading" ? <p className="visit-inline-state"><span className="spinner" aria-hidden="true" />Шукаємо послуги…</p> : null}
            {serviceState === "error" ? <p className="visit-inline-state visit-inline-state--error"><Icon name="warning" />{serviceError}</p> : null}
            {serviceState === "ready" && serviceOptions.length === 0 ? <p className="visit-inline-state">Активних послуг за цим запитом не знайдено.</p> : null}
            {serviceState === "ready" && serviceOptions.length > 0 ? (
              <ul>
                {serviceOptions.map((service) => {
                  const added = serviceLines.some((line) => line.service_id === service.id);
                  return (
                    <li key={service.id}>
                      <div><strong>{service.name}</strong><small>{service.code} · {money(service.price_minor)}</small></div>
                      <button className="button button--secondary" disabled={disabled} onClick={() => { addService(service); }} type="button">
                        {added ? "Додати ще" : "Додати"}
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : null}
          </div>

          {serviceLines.length === 0 ? <p className="visit-lines-empty">Послуги ще не додані. Перед завершенням прийому знадобиться щонайменше одна.</p> : (
            <ul className="visit-draft-lines" aria-label="Послуги чернетки">
              {serviceLines.map((line) => (
                <li key={line.service_id}>
                  <div className="visit-draft-line__identity">
                    <strong>{line.service_name}</strong>
                    <small>{line.service_code} · {money(line.price_minor)} за одиницю</small>
                    {line.is_primary ? <span>Основна із запису</span> : null}
                  </div>
                  <div className="visit-quantity">
                    <button aria-label={`Зменшити кількість ${line.service_name}`} disabled={disabled || line.quantity <= 1} onClick={() => { updateServiceQuantity(line.service_id, line.quantity - 1); }} type="button">−</button>
                    <input aria-label={`Кількість послуги ${line.service_name}`} disabled={disabled} max="99" min="1" onChange={(event) => { updateServiceQuantity(line.service_id, Number(event.target.value)); }} type="number" value={line.quantity} />
                    <button aria-label={`Збільшити кількість ${line.service_name}`} disabled={disabled || line.quantity >= 99} onClick={() => { updateServiceQuantity(line.service_id, line.quantity + 1); }} type="button">+</button>
                  </div>
                  <strong className="visit-draft-line__total">{money(line.price_minor * line.quantity)}</strong>
                  <button aria-label={`Видалити послугу ${line.service_name}`} className="icon-button" disabled={disabled} onClick={() => { onServiceLinesChange(serviceLines.filter((item) => item.service_id !== line.service_id)); }} type="button"><Icon name="close" /></button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="visit-lines-section" aria-labelledby="visit-materials-title">
          <header>
            <div><p className="eyebrow">Матеріали</p><h3 id="visit-materials-title">Фактичне використання</h3><p>Залишок лише перевіряється. Списання відбудеться під час завершення прийому.</p></div>
            <button className="button button--secondary" disabled={disabled} onClick={() => { setMaterialDialogOpen(true); }} type="button"><Icon name="plus" />Додати матеріал</button>
          </header>

          {fieldError ? <p className="visit-inline-state visit-inline-state--error" role="alert"><Icon name="warning" />{fieldError}</p> : null}
          {materialLines.length === 0 ? <p className="visit-lines-empty">Матеріали ще не додані. Чернетку можна зберегти без них.</p> : (
            <ul className="visit-draft-lines visit-draft-lines--materials" aria-label="Матеріали чернетки">
              {materialLines.map((line) => {
                const quantity = decimal(line.quantity);
                const insufficient = !line.is_available || quantity <= 0 || quantity > decimal(line.available_quantity);
                return (
                  <li className={insufficient ? "visit-draft-line--warning" : undefined} key={line.lot_id}>
                    <div className="visit-draft-line__identity">
                      <strong>{line.material_name}</strong>
                      <small>{line.material_sku} · партія {line.lot_number}</small>
                      <span>{line.expires_on === null ? "Без строку" : `Придатна до ${dateFormatter.format(new Date(`${line.expires_on}T12:00:00Z`))}`} · доступно {line.available_quantity} {line.material_unit}</span>
                    </div>
                    <label className="form-field visit-material-quantity">
                      <span>Використано, {line.material_unit}</span>
                      <input aria-label={`Кількість матеріалу ${line.material_name}, партія ${line.lot_number}`} disabled={disabled} max={line.available_quantity} min="0.001" onChange={(event) => { onMaterialLinesChange(materialLines.map((item) => item.lot_id === line.lot_id ? { ...item, quantity: event.target.value } : item)); }} step="0.001" type="number" value={line.quantity} />
                    </label>
                    <button aria-label={`Видалити матеріал ${line.material_name}, партія ${line.lot_number}`} className="icon-button" disabled={disabled} onClick={() => { onMaterialLinesChange(materialLines.filter((item) => item.lot_id !== line.lot_id)); }} type="button"><Icon name="close" /></button>
                    {insufficient ? <p className="field-error">Оновіть партію або кількість: поточного залишку недостатньо.</p> : null}
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>

      {materialDialogOpen ? (
        <div className="modal-layer" role="presentation">
          <section aria-labelledby="visit-material-dialog-title" aria-modal="true" className="modal-card visit-material-dialog" role="dialog">
            <header className="modal-card__header">
              <div><p className="eyebrow">Чернетка прийому</p><h2 id="visit-material-dialog-title">Додати матеріал</h2><p>Виберіть матеріал, доступну партію та фактичну кількість.</p></div>
              <button aria-label="Закрити додавання матеріалу" className="icon-button" onClick={closeMaterialDialog} type="button"><Icon name="close" /></button>
            </header>
            <div className="modal-card__body visit-material-dialog__body">
              <label className="form-field">
                <span>Пошук за назвою або артикулом</span>
                <input autoFocus onChange={(event) => { setMaterialSearch(event.target.value); setSelectedMaterial(null); setSelectedLotId(""); }} placeholder="Наприклад, каполін або KAP-001" type="search" value={materialSearch} />
              </label>
              <div className="visit-option-results visit-material-results" aria-live="polite">
                {materialState === "loading" ? <p className="visit-inline-state"><span className="spinner" aria-hidden="true" />Шукаємо доступні партії…</p> : null}
                {materialState === "error" ? <p className="visit-inline-state visit-inline-state--error" role="alert"><Icon name="warning" />{materialError}</p> : null}
                {materialState === "ready" && materialOptions.length === 0 ? <p className="visit-inline-state">Матеріалів із придатним залишком не знайдено.</p> : null}
                {materialState === "ready" && materialOptions.length > 0 ? <ul>{materialOptions.map((material) => (
                  <li className={selectedMaterial?.id === material.id ? "is-selected" : undefined} key={material.id}>
                    <div><strong>{material.name}</strong><small>{material.sku} · доступно {material.available_quantity} {material.unit}</small></div>
                    <button className="button button--secondary" onClick={() => { chooseMaterial(material); }} type="button">Вибрати</button>
                  </li>
                ))}</ul> : null}
              </div>

              {selectedMaterial ? (
                <div className="visit-material-selection">
                  <div><strong>{selectedMaterial.name}</strong><small>{selectedMaterial.sku} · {selectedMaterial.unit}</small></div>
                  <label className="form-field">
                    <span>Доступна партія</span>
                    <select aria-label="Доступна партія" onChange={(event) => { setSelectedLotId(event.target.value); const lot = selectedMaterial.lots.find((item) => item.id === event.target.value); setMaterialQuantity(lot === undefined ? "" : Math.min(1, decimal(lot.current_quantity)).toFixed(3)); setMaterialError(null); }} value={selectedLotId}>
                      {selectedMaterial.lots.map((lot) => <option key={lot.id} value={lot.id}>#{lot.fefo_rank} · {lot.lot_number} · {lot.expires_on ?? "без строку"} · {lot.current_quantity} {selectedMaterial.unit}</option>)}
                    </select>
                  </label>
                  <label className="form-field">
                    <span>Фактична кількість, {selectedMaterial.unit}</span>
                    <input aria-label={`Фактична кількість, ${selectedMaterial.unit}`} max={selectedLot?.current_quantity} min="0.001" onChange={(event) => { setMaterialQuantity(event.target.value); setMaterialError(null); }} step="0.001" type="number" value={materialQuantity} />
                    {selectedLot ? <small>Доступно в партії: {selectedLot.current_quantity} {selectedMaterial.unit}</small> : null}
                  </label>
                </div>
              ) : null}
              {materialError ? <p className="form-message form-message--error" role="alert"><Icon name="warning" />{materialError}</p> : null}
            </div>
            <footer className="modal-actions">
              <button className="button button--secondary" onClick={closeMaterialDialog} type="button">Скасувати</button>
              <button className="button button--primary" disabled={!materialQuantityValid} onClick={addMaterial} type="button">Додати до чернетки</button>
            </footer>
          </section>
        </div>
      ) : null}
    </>
  );
}
