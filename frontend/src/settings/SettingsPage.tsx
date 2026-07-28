import { useCallback, useEffect, useRef, useState, type SyntheticEvent } from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders } from "../auth/AuthContext";
import { BookingRequestIntegrationSettings } from "./BookingRequestIntegrationSettings";
import { ScheduleSettings } from "./ScheduleSettings";
import { ServiceEditorDialog, type ServiceEditor } from "./ServiceEditorDialog";
import { StatusSettings } from "./StatusSettings";

type ClinicProfile = components["schemas"]["ClinicProfile"];
type Room = components["schemas"]["Room"];
type Service = components["schemas"]["Service"];
type FieldErrors = Readonly<Record<string, readonly string[]>>;
type SettingsSection = "profile" | "rooms" | "services" | "statuses" | "schedule" | "integrations";
type RoomEditor = { readonly mode: "create" } | { readonly mode: "edit"; readonly room: Room };
type ServiceStatus = "all" | "active" | "inactive";

const servicePrice = new Intl.NumberFormat("uk-UA", {
  style: "currency",
  currency: "UAH",
  minimumFractionDigits: 2,
});

interface ProfileDraft {
  readonly name: string;
  readonly phone: string;
  readonly email: string;
  readonly address: string;
  readonly description: string;
}

function profileDraft(profile: ClinicProfile): ProfileDraft {
  return {
    name: profile.name,
    phone: profile.phone,
    email: profile.email,
    address: profile.address,
    description: profile.description ?? "",
  };
}

function fieldMessage(errors: FieldErrors, field: string): string | null {
  return errors[field]?.[0] ?? null;
}

function RoomEditorDialog({
  editor,
  onClose,
  onSaved,
}: {
  readonly editor: RoomEditor;
  readonly onClose: () => void;
  readonly onSaved: (room: Room, message: string) => void;
}) {
  const isCreate = editor.mode === "create";
  const [name, setName] = useState(editor.mode === "edit" ? editor.room.name : "");
  const [isActive, setIsActive] = useState(editor.mode === "edit" ? (editor.room.is_active ?? true) : true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const submit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    setFieldErrors({});
    const result = editor.mode === "create"
      ? await apiClient.POST("/api/v1/rooms", {
          body: { name, is_active: isActive },
          headers: csrfHeaders(),
        }).catch(() => null)
      : await apiClient.PATCH("/api/v1/rooms/{room_id}", {
          params: { path: { room_id: editor.room.id } },
          body: { name, is_active: isActive, version: editor.room.version ?? 1 },
          headers: csrfHeaders(),
        }).catch(() => null);

    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
      setFieldErrors(result.error.fields);
    } else {
      const statusMessage = editor.mode === "edit" && editor.room.is_active !== result.data.is_active
        ? result.data.is_active ? `Кімнату «${result.data.name}» активовано.` : `Кімнату «${result.data.name}» деактивовано.`
        : isCreate ? `Кімнату «${result.data.name}» створено.` : `Кімнату «${result.data.name}» оновлено.`;
      onSaved(result.data, statusMessage);
    }
    setIsSaving(false);
  };

  return (
    <div className="modal-layer" role="dialog" aria-modal="true" aria-labelledby="room-editor-title">
      <form className="modal-card room-editor" onSubmit={(event) => void submit(event)}>
        <header className="modal-card__header">
          <div><p className="eyebrow">Одна локація · ADR-001</p><h2 id="room-editor-title">{isCreate ? "Нова кімната" : "Налаштувати кімнату"}</h2></div>
          <button className="icon-button" onClick={onClose} type="button" aria-label="Закрити форму кімнати"><Icon name="close" /></button>
        </header>
        <p className="modal-intro">Кімнати не видаляються: деактивація лише прибирає їх із нових записів, а історичні назви зберігаються.</p>
        {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div>}
        <label className="form-field"><span>Назва кімнати</span><input autoFocus maxLength={100} onChange={(event) => { setName(event.target.value); }} required value={name} />{fieldMessage(fieldErrors, "name") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "name")}</small>}</label>
        <label className="settings-check"><input checked={isActive} onChange={(event) => { setIsActive(event.target.checked); }} type="checkbox" /><span><strong>Активна кімната</strong><small>Доступна для створення нових записів.</small></span></label>
        {!isCreate && editor.room.is_active && !isActive ? <div className="room-warning"><Icon name="warning" /><span><strong>Кімната стане недоступною для нових записів.</strong><small>Старі й майбутні вже створені записи не змінюються.</small></span></div> : null}
        <div className="modal-actions"><button className="button button--secondary" disabled={isSaving} onClick={onClose} type="button">Скасувати</button><button className={`button ${!isCreate && editor.room.is_active && !isActive ? "button--danger" : "button--primary"}`} disabled={isSaving} type="submit">{isSaving ? "Зберігаємо…" : isCreate ? "Створити кімнату" : "Зберегти зміни"}</button></div>
      </form>
    </div>
  );
}

export function SettingsPage() {
  const [section, setSection] = useState<SettingsSection>("profile");
  const [profile, setProfile] = useState<ClinicProfile | null>(null);
  const [draft, setDraft] = useState<ProfileDraft | null>(null);
  const [rooms, setRooms] = useState<readonly Room[]>([]);
  const [services, setServices] = useState<readonly Service[] | null>(null);
  const [serviceSearch, setServiceSearch] = useState("");
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus>("all");
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingServices, setIsLoadingServices] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [editor, setEditor] = useState<RoomEditor | null>(null);
  const [serviceEditor, setServiceEditor] = useState<ServiceEditor | null>(null);
  const logoInput = useRef<HTMLInputElement>(null);

  const loadSettings = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const [profileResult, roomsResult] = await Promise.all([
      apiClient.GET("/api/v1/clinic-profile").catch(() => null),
      apiClient.GET("/api/v1/rooms").catch(() => null),
    ]);
    if (profileResult === null || roomsResult === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (profileResult.data === undefined) {
      setError(profileResult.error.message);
    } else if (roomsResult.data === undefined) {
      setError(roomsResult.error.message);
    } else {
      setProfile(profileResult.data);
      setDraft(profileDraft(profileResult.data));
      setRooms(roomsResult.data.rooms);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  const loadServices = useCallback(async () => {
    setIsLoadingServices(true);
    setError(null);
    const result = await apiClient.GET("/api/v1/services", {
      params: { query: { status: "all" } },
    }).catch(() => null);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
    } else {
      setServices(result.data.services);
    }
    setIsLoadingServices(false);
  }, []);

  const updateDraft = <Key extends keyof ProfileDraft>(key: Key, value: ProfileDraft[Key]) => {
    setDraft((current) => current === null ? current : { ...current, [key]: value });
  };

  const saveProfile = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    if (profile === null || draft === null) {
      return;
    }
    setIsSaving(true);
    setError(null);
    setSuccess(null);
    setFieldErrors({});
    const result = await apiClient.PATCH("/api/v1/clinic-profile", {
      body: { ...draft, version: profile.version ?? 1 },
      headers: csrfHeaders(),
    }).catch(() => null);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
      setFieldErrors(result.error.fields);
    } else {
      setProfile(result.data);
      setDraft(profileDraft(result.data));
      setSuccess("Профіль кабінету збережено.");
    }
    setIsSaving(false);
  };

  const uploadLogo = async (file: File | undefined) => {
    if (file === undefined || profile === null) {
      return;
    }
    setError(null);
    setSuccess(null);
    setFieldErrors({});
    if (!["image/png", "image/jpeg"].includes(file.type) || file.size > 5 * 1024 * 1024) {
      setError("Оберіть PNG або JPEG розміром не більше 5 МБ.");
      return;
    }
    setIsUploading(true);
    const result = await apiClient.PUT("/api/v1/clinic-profile/logo", {
      body: { logo: file.name, version: profile.version ?? 1 },
      bodySerializer: () => {
        const body = new FormData();
        body.append("logo", file);
        body.append("version", String(profile.version ?? 1));
        return body;
      },
      headers: csrfHeaders(),
    }).catch(() => null);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
      setFieldErrors(result.error.fields);
    } else {
      setProfile(result.data);
      setDraft(profileDraft(result.data));
      setSuccess("Новий приватний логотип збережено.");
    }
    setIsUploading(false);
    if (logoInput.current !== null) {
      logoInput.current.value = "";
    }
  };

  const replaceRoom = (room: Room, message: string) => {
    setRooms((current) => {
      const found = current.some((item) => item.id === room.id);
      const next = found ? current.map((item) => item.id === room.id ? room : item) : [...current, room];
      return [...next].sort((left, right) => Number(right.is_active) - Number(left.is_active) || left.name.localeCompare(right.name, "uk"));
    });
    setEditor(null);
    setSuccess(message);
    setError(null);
  };

  const replaceService = (service: Service, message: string) => {
    setServices((current) => {
      const list = current ?? [];
      const found = list.some((item) => item.id === service.id);
      const next = found ? list.map((item) => item.id === service.id ? service : item) : [...list, service];
      return [...next].sort((left, right) => Number(right.is_active) - Number(left.is_active) || left.name.localeCompare(right.name, "uk"));
    });
    setServiceEditor(null);
    setSuccess(message);
    setError(null);
  };

  const activeRoomCount = rooms.filter((room) => room.is_active).length;
  const serviceList = services ?? [];
  const activeServiceCount = serviceList.filter((service) => service.is_active).length;
  const normalizedServiceSearch = serviceSearch.trim().toLocaleLowerCase("uk");
  const visibleServices = serviceList.filter((service) => {
    const matchesSearch = normalizedServiceSearch === ""
      || service.code.toLocaleLowerCase("uk").includes(normalizedServiceSearch)
      || service.name.toLocaleLowerCase("uk").includes(normalizedServiceSearch);
    const matchesStatus = serviceStatus === "all"
      || (serviceStatus === "active" ? service.is_active : !service.is_active);
    return matchesSearch && matchesStatus;
  });

  return (
    <>
      <header className="page-heading settings-heading">
        <div><p className="eyebrow">Керування · TP-204–206</p><h1>Налаштування кабінету</h1><p>Одна локація без філій: профіль, довідники, системні статуси та спільний робочий час.</p></div>
        <span className="admin-only-badge"><Icon name="lock" />Тільки адміністратор</span>
      </header>

      {error === null ? null : <div className="form-message form-message--error page-message" role="alert"><Icon name="warning" /><span>{error}</span>{error.includes("іншій сесії") ? <button className="text-action" onClick={() => void loadSettings()} type="button">Оновити дані</button> : null}</div>}
      {success === null ? null : <div className="form-message form-message--success page-message" role="status"><Icon name="settings" /><span>{success}</span></div>}

      <nav className="settings-tabs" aria-label="Розділи налаштувань">
        <button className={section === "profile" ? "active" : undefined} data-testid="settings-profile-tab" onClick={() => { setSection("profile"); setSuccess(null); }} type="button"><Icon name="overview" /><span><strong>Профіль кабінету</strong><small>Логотип і контакти</small></span></button>
        <button className={section === "rooms" ? "active" : undefined} data-testid="settings-rooms-tab" onClick={() => { setSection("rooms"); setSuccess(null); }} type="button"><Icon name="calendar" /><span><strong>Кімнати</strong><small>{activeRoomCount} активних</small></span></button>
        <button className={section === "services" ? "active" : undefined} data-testid="settings-services-tab" onClick={() => { setSection("services"); setSuccess(null); if (services === null) void loadServices(); }} type="button"><Icon name="finance" /><span><strong>Послуги</strong><small>{services === null ? "Каталог" : <>{activeServiceCount} активних</>}</small></span></button>
        <button className={section === "statuses" ? "active" : undefined} data-testid="settings-statuses-tab" onClick={() => { setSection("statuses"); setSuccess(null); }} type="button"><Icon name="tasks" /><span><strong>Статуси</strong><small>8 системних</small></span></button>
        <button className={section === "schedule" ? "active" : undefined} data-testid="settings-schedule-tab" onClick={() => { setSection("schedule"); setSuccess(null); }} type="button"><Icon name="calendar" /><span><strong>Робочий час</strong><small>Спільний графік</small></span></button>
        <button className={section === "integrations" ? "active" : undefined} data-testid="settings-integrations-tab" onClick={() => { setSection("integrations"); setSuccess(null); }} type="button"><Icon name="code" /><span><strong>Інтеграції</strong><small>API заявок</small></span></button>
      </nav>

      {isLoading ? <section className="panel settings-state"><span className="spinner" /><p>Завантажуємо налаштування…</p></section> : null}

      {!isLoading && section === "profile" && profile !== null && draft !== null ? (
        <form className="settings-profile-layout" onSubmit={(event) => void saveProfile(event)}>
          <section className="panel settings-card settings-brand-card">
            <header><div><p className="eyebrow">Ідентичність</p><h2>Профіль кабінету</h2><p>Ці дані використовуються працівниками в CRM.</p></div><span className="single-location-badge">Одна локація</span></header>
            <div className="clinic-logo-row">
              <div className="clinic-logo" aria-live="polite">{profile.has_logo && profile.logo_url !== null ? <img alt={`Логотип ${profile.name}`} src={profile.logo_url} /> : <><strong>P</strong><small>PODORIA</small></>}</div>
              <div><strong>Логотип кабінету</strong><p>Приватний PNG або JPEG до 5 МБ. Файл доступний лише автентифікованим працівникам.</p><button className="button button--secondary" disabled={isUploading} onClick={() => { logoInput.current?.click(); }} type="button">{isUploading ? "Завантажуємо…" : profile.has_logo ? "Замінити логотип" : "Додати логотип"}</button><input accept="image/png,image/jpeg" aria-label="Файл логотипа" className="sr-only" onChange={(event) => void uploadLogo(event.target.files?.[0])} ref={logoInput} type="file" />{fieldMessage(fieldErrors, "logo") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "logo")}</small>}</div>
            </div>
          </section>

          <section className="panel settings-card settings-contact-card">
            <header><div><p className="eyebrow">Контакти</p><h2>Дані кабінету</h2><p>Усі обов’язкові поля зі специфікації §17.1.</p></div></header>
            <div className="settings-form-grid">
              <label className="form-field settings-wide"><span>Назва кабінету</span><input maxLength={160} onChange={(event) => { updateDraft("name", event.target.value); }} required value={draft.name} />{fieldMessage(fieldErrors, "name") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "name")}</small>}</label>
              <label className="form-field"><span>Телефон</span><input autoComplete="tel" maxLength={32} onChange={(event) => { updateDraft("phone", event.target.value); }} required value={draft.phone} />{fieldMessage(fieldErrors, "phone") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "phone")}</small>}</label>
              <label className="form-field"><span>Email</span><input autoComplete="email" maxLength={254} onChange={(event) => { updateDraft("email", event.target.value); }} required type="email" value={draft.email} />{fieldMessage(fieldErrors, "email") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "email")}</small>}</label>
              <label className="form-field settings-wide"><span>Адреса</span><input autoComplete="street-address" maxLength={255} onChange={(event) => { updateDraft("address", event.target.value); }} required value={draft.address} />{fieldMessage(fieldErrors, "address") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "address")}</small>}</label>
              <label className="form-field settings-wide"><span>Короткий опис <small>необов’язково</small></span><textarea maxLength={1000} onChange={(event) => { updateDraft("description", event.target.value); }} rows={4} value={draft.description} />{fieldMessage(fieldErrors, "description") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "description")}</small>}</label>
            </div>
            <footer><span>Філії та тип кабінету не використовуються.</span><button className="button button--primary" disabled={isSaving} type="submit">{isSaving ? "Зберігаємо…" : "Зберегти профіль"}</button></footer>
          </section>
        </form>
      ) : null}

      {!isLoading && section === "rooms" ? (
        <section className="panel rooms-panel">
          <header><div><p className="eyebrow">Ресурси розкладу</p><h2>Кімнати кабінету</h2><p>Активна кімната буде обов’язковою для нового запису. Деактивація не стирає історію.</p></div><button className="button button--primary" onClick={() => { setEditor({ mode: "create" }); setSuccess(null); }} type="button"><Icon name="plus" />Додати кімнату</button></header>
          <div className="room-summary"><span><strong>{rooms.length}</strong> усього</span><span><strong>{activeRoomCount}</strong> активних</span><span><strong>{rooms.length - activeRoomCount}</strong> неактивних</span></div>
          {rooms.length === 0 ? <div className="settings-state"><Icon name="empty" /><h3>Кімнат ще немає</h3><p>Створіть першу кімнату, щоб підготувати довідник для календаря.</p><button className="button button--primary" onClick={() => { setEditor({ mode: "create" }); }} type="button">Створити кімнату</button></div> : (
            <div className="room-grid">{rooms.map((room) => <article className={room.is_active ? "room-card" : "room-card room-card--inactive"} key={room.id}><span className="room-card__icon"><Icon name="calendar" /></span><div><strong>{room.name}</strong><small>{room.is_active ? "Доступна для нових записів" : "Не пропонується в нових записах"}</small></div><span className={`profile-status profile-status--${room.is_active ? "active" : "inactive"}`}><span />{room.is_active ? "Активна" : "Неактивна"}</span><button className="button button--secondary" onClick={() => { setEditor({ mode: "edit", room }); setSuccess(null); }} type="button">Налаштувати</button></article>)}</div>
          )}
          <footer className="rooms-history-note"><Icon name="lock" /><span><strong>Історичні зв’язки захищено</strong><small>Кімнати не видаляються через API; записи зберігатимуть snapshot назви.</small></span></footer>
        </section>
      ) : null}

      {!isLoading && section === "services" ? (
        <section className="panel services-panel">
          <header><div><p className="eyebrow">Каталог для записів</p><h2>Послуги кабінету</h2><p>Код, тривалість, ціна й колір календаря. Неактивні послуги залишаються в історії.</p></div><button className="button button--primary" onClick={() => { setServiceEditor({ mode: "create" }); setSuccess(null); }} type="button"><Icon name="plus" />Додати послугу</button></header>

          {isLoadingServices ? <div className="settings-state services-loading"><span className="spinner" /><p>Завантажуємо каталог послуг…</p></div> : null}

          {!isLoadingServices && services !== null ? (
            <>
              <div className="room-summary service-summary"><span><strong>{serviceList.length}</strong> усього</span><span><strong>{activeServiceCount}</strong> активних</span><span><strong>{serviceList.length - activeServiceCount}</strong> неактивних</span></div>
              <div className="service-toolbar">
                <label className="form-field service-search"><span>Пошук</span><span className="input-with-icon"><Icon name="search" /><input onChange={(event) => { setServiceSearch(event.target.value); }} placeholder="Код або назва" value={serviceSearch} /></span></label>
                <label className="form-field"><span>Статус</span><select onChange={(event) => { setServiceStatus(event.target.value as ServiceStatus); }} value={serviceStatus}><option value="all">Усі послуги</option><option value="active">Активні</option><option value="inactive">Неактивні</option></select></label>
                <button className="icon-button" disabled={serviceSearch === "" && serviceStatus === "all"} onClick={() => { setServiceSearch(""); setServiceStatus("all"); }} type="button" aria-label="Скинути фільтри"><Icon name="refresh" /></button>
              </div>

              {visibleServices.length === 0 ? <div className="settings-state"><Icon name="empty" /><h3>{serviceList.length === 0 ? "Послуг ще немає" : "Послуг не знайдено"}</h3><p>{serviceList.length === 0 ? "Створіть першу послугу для майбутніх записів і візитів." : "Змініть пошук або статус, щоб побачити інші позиції каталогу."}</p>{serviceList.length === 0 ? <button className="button button--primary" onClick={() => { setServiceEditor({ mode: "create" }); }} type="button">Створити послугу</button> : <button className="button button--secondary" onClick={() => { setServiceSearch(""); setServiceStatus("all"); }} type="button">Скинути фільтри</button>}</div> : (
                <div className="service-table">
                  <div className="service-table__head" aria-hidden="true"><span>Послуга</span><span>Тривалість</span><span>Ціна</span><span>Статус</span><span /></div>
                  {visibleServices.map((service) => <article className={service.is_active ? "service-row" : "service-row service-row--inactive"} key={service.id}><div className="service-identity"><span className="service-color" style={{ backgroundColor: service.color }} /><span><strong>{service.name}</strong><small>{service.code}</small></span></div><span className="service-metric" data-label="Тривалість"><strong>{service.duration_minutes}</strong> хв</span><span className="service-metric service-price" data-label="Ціна">{servicePrice.format(service.price_minor / 100)}</span><span className={`profile-status profile-status--${service.is_active ? "active" : "inactive"}`}><span />{service.is_active ? "Активна" : "Неактивна"}</span><button className="button button--secondary" onClick={() => { setServiceEditor({ mode: "edit", service }); setSuccess(null); }} type="button" aria-label={`Редагувати ${service.name}`}>Редагувати</button></article>)}
                </div>
              )}
              <footer className="rooms-history-note"><Icon name="lock" /><span><strong>Без фізичного видалення</strong><small>Неактивна послуга не пропонується в нових записах, але її код, назва й ціна залишаються в історії.</small></span></footer>
            </>
          ) : null}
        </section>
      ) : null}

      {!isLoading && section === "statuses" ? <StatusSettings /> : null}
      {!isLoading && section === "schedule" ? <ScheduleSettings /> : null}
      {!isLoading && section === "integrations" ? <BookingRequestIntegrationSettings /> : null}

      {editor === null ? null : <RoomEditorDialog editor={editor} onClose={() => { setEditor(null); }} onSaved={replaceRoom} />}
      {serviceEditor === null ? null : <ServiceEditorDialog editor={serviceEditor} onClose={() => { setServiceEditor(null); }} onSaved={replaceService} />}
    </>
  );
}
