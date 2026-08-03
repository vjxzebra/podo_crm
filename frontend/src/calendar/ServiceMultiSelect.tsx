import { useMemo, useState, type CSSProperties } from "react";

import type { components } from "../api/schema";
import { Icon } from "../app/Icon";

type Service = components["schemas"]["Service"];

interface ServiceMultiSelectProps {
  readonly error?: string | null;
  readonly isLoading?: boolean;
  readonly onChange: (serviceIds: readonly string[]) => void;
  readonly selectedIds: readonly string[];
  readonly services: readonly Service[];
}

function searchable(value: string): string {
  return value.trim().toLocaleLowerCase("uk-UA");
}

export function ServiceMultiSelect({
  error,
  isLoading = false,
  onChange,
  selectedIds,
  services,
}: ServiceMultiSelectProps) {
  const [search, setSearch] = useState("");
  const selected = useMemo(
    () => selectedIds.flatMap((id) => {
      const service = services.find((item) => item.id === id);
      return service === undefined ? [] : [service];
    }),
    [selectedIds, services],
  );
  const filtered = useMemo(() => {
    const term = searchable(search);
    if (!term) return services;
    return services.filter((service) =>
      searchable(`${service.name} ${service.code}`).includes(term));
  }, [search, services]);
  const totalDuration = selected.reduce(
    (total, service) => total + service.duration_minutes,
    0,
  );

  return (
    <fieldset className="service-multiselect appointment-form-wide">
      <legend>Послуги · обов’язково</legend>
      <label className="service-multiselect__search">
        <Icon name="search" />
        <span className="visually-hidden">Пошук послуги</span>
        <input
          aria-label="Пошук послуги"
          disabled={isLoading}
          onChange={(event) => { setSearch(event.target.value); }}
          placeholder={isLoading ? "Завантажуємо послуги…" : "Назва або код послуги"}
          type="search"
          value={search}
        />
      </label>
      <div aria-label="Доступні послуги" className="service-multiselect__options" role="group">
        {filtered.map((service) => {
          const checked = selectedIds.includes(service.id);
          return (
            <label className={`service-multiselect__option ${checked ? "service-multiselect__option--selected" : ""}`} key={service.id}>
              <input
                aria-label={`Обрати послугу ${service.name}`}
                checked={checked}
                onChange={(event) => {
                  onChange(event.target.checked
                    ? [...selectedIds, service.id]
                    : selectedIds.filter((id) => id !== service.id));
                }}
                type="checkbox"
              />
              <span
                aria-hidden="true"
                className="service-color-dot"
                style={{ "--service-color": service.color } as CSSProperties}
              />
              <span><strong>{service.name}</strong><small>{service.code} · {service.duration_minutes} хв</small></span>
            </label>
          );
        })}
        {!isLoading && filtered.length === 0 ? (
          <p className="service-multiselect__empty">Послуг за цим запитом не знайдено.</p>
        ) : null}
      </div>
      {selected.length > 0 ? (
        <div className="service-multiselect__selected" aria-live="polite">
          <span>Обрано: {selected.length} · разом {totalDuration} хв</span>
          <div>
            {selected.map((service) => (
              <button
                aria-label={`Видалити послугу ${service.name}`}
                key={service.id}
                onClick={() => { onChange(selectedIds.filter((id) => id !== service.id)); }}
                style={{ "--service-color": service.color } as CSSProperties}
                type="button"
              >
                <span aria-hidden="true" />{service.name}<b aria-hidden="true">×</b>
              </button>
            ))}
          </div>
        </div>
      ) : <small className="service-multiselect__hint">Можна обрати декілька послуг.</small>}
      {error ? <small className="field-error">{error}</small> : null}
    </fieldset>
  );
}
