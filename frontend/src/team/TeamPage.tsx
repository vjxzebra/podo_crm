import { useCallback, useEffect, useState, type SyntheticEvent } from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders, roleLabels, type UserRole } from "../auth/AuthContext";

type TeamUser = components["schemas"]["TeamUser"];
type StatusFilter = "all" | "active" | "inactive";
type FieldErrors = Readonly<Record<string, readonly string[]>>;

const roleAccess: Record<UserRole, string> = {
  podologist: "Власний календар, доступ до медичних даних і оформлення призначених прийомів.",
  reception: "Спільний календар, пацієнти, справи, оплати та власна касова зміна без медичних даних.",
  admin: "Повне керування кабінетом, командою, складом, аналітикою, аудитом і налаштуваннями.",
};

type EditorState =
  | { readonly mode: "create" }
  | { readonly mode: "edit"; readonly user: TeamUser };

interface UserFormState {
  readonly firstName: string;
  readonly lastName: string;
  readonly phone: string;
  readonly email: string;
  readonly role: UserRole;
  readonly isActive: boolean;
  readonly mustChangePassword: boolean;
  readonly temporaryPassword: string;
  readonly confirmation: string;
}

function initialForm(editor: EditorState): UserFormState {
  const user = editor.mode === "edit" ? editor.user : undefined;
  return {
    firstName: user?.first_name ?? "",
    lastName: user?.last_name ?? "",
    phone: user?.phone ?? "",
    email: user?.email ?? "",
    role: user?.role ?? "podologist",
    isActive: user?.is_active ?? true,
    mustChangePassword: user?.must_change_password ?? true,
    temporaryPassword: "",
    confirmation: "",
  };
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toLocaleUpperCase("uk");
}

function formatActivity(value: string | null): string {
  if (value === null) {
    return "Ще не входив";
  }
  return new Intl.DateTimeFormat("uk-UA", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function fieldMessage(errors: FieldErrors, field: string): string | null {
  return errors[field]?.[0] ?? null;
}

function UserEditorDialog({
  editor,
  onClose,
  onSaved,
}: {
  readonly editor: EditorState;
  readonly onClose: () => void;
  readonly onSaved: (user: TeamUser, message: string) => void;
}) {
  const [form, setForm] = useState<UserFormState>(() => initialForm(editor));
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const isCreate = editor.mode === "create";

  const update = <Key extends keyof UserFormState>(key: Key, value: UserFormState[Key]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const submit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    setError(null);
    setFieldErrors({});
    if (isCreate && form.temporaryPassword !== form.confirmation) {
      setFieldErrors({ temporary_password_confirmation: ["Паролі не збігаються."] });
      return;
    }
    setIsSaving(true);
    const result = editor.mode === "create"
      ? await apiClient
          .POST("/api/v1/users", {
            body: {
              first_name: form.firstName,
              last_name: form.lastName,
              phone: form.phone,
              email: form.email,
              role: form.role,
              temporary_password: form.temporaryPassword,
              temporary_password_confirmation: form.confirmation,
              is_active: form.isActive,
              must_change_password: form.mustChangePassword,
            },
            headers: csrfHeaders(),
          })
          .catch(() => null)
      : await apiClient
          .PATCH("/api/v1/users/{user_id}", {
            params: { path: { user_id: editor.user.id } },
            body: {
              first_name: form.firstName,
              last_name: form.lastName,
              phone: form.phone,
              email: form.email,
              role: form.role,
              ...(editor.user.is_active === form.isActive ? {} : { is_active: form.isActive }),
            },
            headers: csrfHeaders(),
          })
          .catch(() => null);

    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
      setFieldErrors(result.error.fields);
    } else {
      onSaved(
        result.data,
        isCreate
          ? `Профіль ${result.data.display_name} створено.`
          : `Профіль ${result.data.display_name} оновлено.`,
      );
    }
    setIsSaving(false);
  };

  return (
    <div className="modal-layer" role="dialog" aria-modal="true" aria-labelledby="team-editor-title">
      <form className="modal-card team-editor" onSubmit={(event) => void submit(event)}>
        <header className="modal-card__header">
          <div>
            <p className="eyebrow">Команда · TP-203</p>
            <h2 id="team-editor-title">{isCreate ? "Новий працівник" : "Редагувати працівника"}</h2>
          </div>
          <button className="icon-button" onClick={onClose} type="button" aria-label="Закрити форму">
            <Icon name="close" />
          </button>
        </header>
        {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div>}
        <div className="team-form-grid">
          <label className="form-field"><span>Ім’я</span><input autoComplete="given-name" onChange={(event) => { update("firstName", event.target.value); }} required value={form.firstName} />{fieldMessage(fieldErrors, "first_name") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "first_name")}</small>}</label>
          <label className="form-field"><span>Прізвище</span><input autoComplete="family-name" onChange={(event) => { update("lastName", event.target.value); }} required value={form.lastName} />{fieldMessage(fieldErrors, "last_name") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "last_name")}</small>}</label>
        </div>
        <label className="form-field"><span>Робочий email</span><input autoComplete="email" onChange={(event) => { update("email", event.target.value); }} required type="email" value={form.email} />{fieldMessage(fieldErrors, "email") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "email")}</small>}</label>
        <label className="form-field"><span>Телефон</span><input autoComplete="tel" onChange={(event) => { update("phone", event.target.value); }} value={form.phone} />{fieldMessage(fieldErrors, "phone") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "phone")}</small>}</label>
        <label className="form-field"><span>Роль</span><select onChange={(event) => { update("role", event.target.value as UserRole); }} value={form.role}>{Object.entries(roleLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>{fieldMessage(fieldErrors, "role") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "role")}</small>}</label>
        <div className="role-access-note"><Icon name="lock" /><span><strong>Доступ ролі «{roleLabels[form.role]}»</strong><small>{roleAccess[form.role]}</small></span></div>

        {isCreate ? (
          <>
            <div className="team-form-grid">
              <label className="form-field"><span>Тимчасовий пароль</span><input autoComplete="new-password" minLength={8} onChange={(event) => { update("temporaryPassword", event.target.value); }} required type="password" value={form.temporaryPassword} />{fieldMessage(fieldErrors, "temporary_password") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "temporary_password")}</small>}</label>
              <label className="form-field"><span>Повторіть пароль</span><input autoComplete="new-password" minLength={8} onChange={(event) => { update("confirmation", event.target.value); }} required type="password" value={form.confirmation} />{fieldMessage(fieldErrors, "temporary_password_confirmation") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "temporary_password_confirmation")}</small>}</label>
            </div>
            <div className="team-checks">
              <label><input checked={form.isActive} onChange={(event) => { update("isActive", event.target.checked); }} type="checkbox" /><span><strong>Активний профіль</strong><small>Працівник може увійти одразу після створення.</small></span></label>
              <label><input checked={form.mustChangePassword} onChange={(event) => { update("mustChangePassword", event.target.checked); }} type="checkbox" /><span><strong>Змінити пароль під час першого входу</strong><small>Тимчасовий пароль діє обмежений час.</small></span></label>
            </div>
          </>
        ) : !editor.user.is_active ? (
          <label className="team-reactivate"><input checked={form.isActive} onChange={(event) => { update("isActive", event.target.checked); }} type="checkbox" /><span><strong>Активувати профіль</strong><small>Якщо пароль тимчасовий, строк його дії почнеться з активації.</small></span></label>
        ) : null}

        <div className="modal-actions">
          <button className="button button--secondary" disabled={isSaving} onClick={onClose} type="button">Скасувати</button>
          <button className="button button--primary" disabled={isSaving} type="submit">{isSaving ? "Зберігаємо…" : isCreate ? "Створити працівника" : "Зберегти зміни"}</button>
        </div>
      </form>
    </div>
  );
}

function TemporaryPasswordDialog({
  user,
  onClose,
  onSaved,
}: {
  readonly user: TeamUser;
  readonly onClose: () => void;
  readonly onSaved: (user: TeamUser, message: string) => void;
}) {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    setError(null);
    if (password !== confirmation) {
      setError("Паролі не збігаються.");
      return;
    }
    setIsSaving(true);
    const result = await apiClient
      .POST("/api/v1/users/{user_id}/temporary-password", {
        params: { path: { user_id: user.id } },
        body: {
          temporary_password: password,
          temporary_password_confirmation: confirmation,
        },
        headers: csrfHeaders(),
      })
      .catch(() => null);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(
        result.error.fields.temporary_password?.[0]
          ?? result.error.fields.temporary_password_confirmation?.[0]
          ?? result.error.message,
      );
    } else {
      onSaved(
        {
          ...user,
          must_change_password: true,
          temporary_password_expires_at: result.data.temporary_password_expires_at,
        },
        `Тимчасовий пароль для ${user.display_name} встановлено; попередні сесії відкликано.`,
      );
    }
    setIsSaving(false);
  };

  return (
    <div className="modal-layer" role="dialog" aria-modal="true" aria-labelledby="team-password-title">
      <form className="modal-card password-modal" onSubmit={(event) => void submit(event)}>
        <header className="modal-card__header"><div><p className="eyebrow">Тимчасовий доступ</p><h2 id="team-password-title">Новий пароль для {user.display_name}</h2></div><button className="icon-button" onClick={onClose} type="button" aria-label="Закрити форму пароля"><Icon name="close" /></button></header>
        <p className="modal-intro">Усі чинні сесії працівника будуть відкликані. Новий пароль передайте вручну після позасистемної перевірки.</p>
        {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div>}
        <label className="form-field"><span>Тимчасовий пароль</span><input autoComplete="new-password" minLength={8} onChange={(event) => { setPassword(event.target.value); }} required type="password" value={password} /></label>
        <label className="form-field"><span>Повторіть тимчасовий пароль</span><input autoComplete="new-password" minLength={8} onChange={(event) => { setConfirmation(event.target.value); }} required type="password" value={confirmation} /></label>
        <div className="modal-actions"><button className="button button--secondary" disabled={isSaving} onClick={onClose} type="button">Скасувати</button><button className="button button--primary" disabled={isSaving} type="submit">{isSaving ? "Зберігаємо…" : "Встановити пароль"}</button></div>
      </form>
    </div>
  );
}

function DeactivateDialog({
  user,
  onClose,
  onConfirmed,
  isSaving,
  error,
}: {
  readonly user: TeamUser;
  readonly onClose: () => void;
  readonly onConfirmed: () => void;
  readonly isSaving: boolean;
  readonly error: string | null;
}) {
  return (
    <div className="modal-layer" role="alertdialog" aria-modal="true" aria-labelledby="deactivate-title" aria-describedby="deactivate-description">
      <section className="modal-card confirm-card">
        <span className="confirm-card__icon"><Icon name="warning" /></span>
        <h2 id="deactivate-title">Деактивувати {user.display_name}?</h2>
        <p id="deactivate-description">Працівник одразу втратить доступ, але його історичні записи, прийоми, касові операції та дії залишаться в системі.</p>
        {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div>}
        <div className="modal-actions"><button className="button button--secondary" disabled={isSaving} onClick={onClose} type="button">Скасувати</button><button className="button button--danger" disabled={isSaving} onClick={onConfirmed} type="button">{isSaving ? "Деактивуємо…" : "Деактивувати профіль"}</button></div>
      </section>
    </div>
  );
}

export function TeamPage() {
  const [users, setUsers] = useState<readonly TeamUser[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [passwordUser, setPasswordUser] = useState<TeamUser | null>(null);
  const [deactivateUser, setDeactivateUser] = useState<TeamUser | null>(null);
  const [isDeactivating, setIsDeactivating] = useState(false);
  const [deactivateError, setDeactivateError] = useState<string | null>(null);

  const loadUsers = useCallback(async (nextSearch: string, nextStatus: StatusFilter) => {
    setIsLoading(true);
    setError(null);
    const result = await apiClient
      .GET("/api/v1/users", {
        params: {
          query: {
            status: nextStatus,
            ...(nextSearch ? { search: nextSearch } : {}),
          },
        },
      })
      .catch(() => null);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
    } else {
      setUsers(result.data.users);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    void loadUsers("", "all");
  }, [loadUsers]);

  const replaceUser = (user: TeamUser, message: string) => {
    setUsers((current) => {
      const exists = current.some((item) => item.id === user.id);
      return exists ? current.map((item) => item.id === user.id ? user : item) : [user, ...current];
    });
    setSuccess(message);
    setEditor(null);
    setPasswordUser(null);
  };

  const deactivate = async () => {
    if (deactivateUser === null) {
      return;
    }
    setIsDeactivating(true);
    setDeactivateError(null);
    const result = await apiClient
      .POST("/api/v1/users/{user_id}/deactivate", {
        params: { path: { user_id: deactivateUser.id } },
        headers: csrfHeaders(),
      })
      .catch(() => null);
    if (result === null) {
      setDeactivateError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setDeactivateError(result.error.message);
    } else {
      replaceUser(result.data, `Профіль ${result.data.display_name} деактивовано.`);
      setDeactivateUser(null);
    }
    setIsDeactivating(false);
  };

  return (
    <>
      <header className="page-heading team-heading">
        <div><p className="eyebrow">Керування · TP-203</p><h1>Команда</h1><p>Працівники, фіксовані ролі, статус доступу й тимчасові паролі. Історичні зв’язки зберігаються після деактивації.</p></div>
        <button className="button button--primary" onClick={() => { setEditor({ mode: "create" }); setSuccess(null); }} type="button"><Icon name="plus" />Додати працівника</button>
      </header>

      {error === null ? null : <div className="form-message form-message--error page-message" role="alert"><Icon name="warning" /><span>{error}</span></div>}
      {success === null ? null : <div className="form-message form-message--success page-message" role="status"><Icon name="team" /><span>{success}</span></div>}

      <section className="panel team-panel" aria-label="Список працівників">
        <form className="team-toolbar" onSubmit={(event) => { event.preventDefault(); void loadUsers(search, status); }} role="search">
          <label className="team-search"><Icon name="search" /><span className="sr-only">Пошук працівників</span><input aria-label="Пошук працівників" onChange={(event) => { setSearch(event.target.value); }} placeholder="Ім’я, email або телефон" value={search} /></label>
          <label className="team-status-filter"><span>Статус</span><select aria-label="Статус профілю" onChange={(event) => { const next = event.target.value as StatusFilter; setStatus(next); void loadUsers(search, next); }} value={status}><option value="all">Усі профілі</option><option value="active">Активні</option><option value="inactive">Неактивні</option></select></label>
          <button className="button button--secondary" disabled={isLoading} type="submit">Знайти</button>
          <button className="icon-button" disabled={isLoading} onClick={() => void loadUsers(search, status)} type="button" aria-label="Оновити список"><Icon name="refresh" /></button>
        </form>

        {isLoading ? <div className="queue-state"><span className="spinner" /><p>Завантажуємо команду…</p></div> : null}
        {!isLoading && users.length === 0 ? <div className="queue-state"><Icon name="team" /><h2>Працівників не знайдено</h2><p>Змініть пошук або фільтр чи створіть новий профіль.</p></div> : null}
        {!isLoading && users.length > 0 ? (
          <div className="team-table-wrap">
            <table className="team-table">
              <thead><tr><th>Працівник</th><th>Роль</th><th>Телефон</th><th>Статус</th><th>Остання активність</th><th><span className="sr-only">Дії</span></th></tr></thead>
              <tbody>{users.map((user) => (
                <tr key={user.id} className={user.is_active ? undefined : "team-row--inactive"}>
                  <td data-label="Працівник"><span className="team-person"><span className="avatar" aria-hidden="true">{initials(user.display_name)}</span><span><strong>{user.display_name}</strong><small>{user.email}</small></span></span></td>
                  <td data-label="Роль"><span className="role-pill">{roleLabels[user.role]}</span></td>
                  <td data-label="Телефон">{user.phone || "—"}</td>
                  <td data-label="Статус"><span className={`profile-status profile-status--${user.is_active ? "active" : "inactive"}`}><span />{user.is_active ? "Активний" : "Неактивний"}</span></td>
                  <td data-label="Остання активність">{formatActivity(user.last_login)}</td>
                  <td data-label="Дії"><div className="team-actions"><button aria-label={`Редагувати ${user.display_name}`} onClick={() => { setEditor({ mode: "edit", user }); setSuccess(null); }} type="button">Редагувати</button>{user.is_active ? <><button aria-label={`Змінити пароль ${user.display_name}`} onClick={() => { setPasswordUser(user); setSuccess(null); }} type="button">Пароль</button><button aria-label={`Деактивувати ${user.display_name}`} className="team-action--danger" onClick={() => { setDeactivateUser(user); setDeactivateError(null); setSuccess(null); }} type="button">Деактивувати</button></> : null}</div></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : null}
      </section>

      {editor === null ? null : <UserEditorDialog editor={editor} onClose={() => { setEditor(null); }} onSaved={replaceUser} />}
      {passwordUser === null ? null : <TemporaryPasswordDialog user={passwordUser} onClose={() => { setPasswordUser(null); }} onSaved={replaceUser} />}
      {deactivateUser === null ? null : <DeactivateDialog error={deactivateError} isSaving={isDeactivating} onClose={() => { setDeactivateUser(null); }} onConfirmed={() => void deactivate()} user={deactivateUser} />}
    </>
  );
}
