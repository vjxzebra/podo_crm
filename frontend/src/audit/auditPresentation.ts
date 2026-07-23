import type { AuditEventDetail, AuditSection } from "./auditApi";

export const auditSectionOptions: readonly { readonly value: AuditSection; readonly label: string }[] = [
  { value: "accounts", label: "Доступ" },
  { value: "team", label: "Команда" },
  { value: "settings", label: "Налаштування" },
  { value: "patients", label: "Пацієнти" },
  { value: "work_items", label: "Справи" },
  { value: "scheduling", label: "Записи" },
  { value: "medical", label: "Медична картка" },
  { value: "visits", label: "Прийоми" },
  { value: "billing", label: "Оплати" },
  { value: "cash", label: "Каса" },
  { value: "inventory", label: "Склад" },
] as const;

const sectionLabelMap: Readonly<Record<string, string>> = Object.fromEntries(
  auditSectionOptions.map((item) => [item.value, item.label]),
);

const actionLabels: Readonly<Record<string, string>> = {
  "accounts.password_changed": "Змінено пароль",
  "accounts.password_reset_requested": "Створено запит на відновлення",
  "accounts.temporary_password_set": "Встановлено тимчасовий пароль",
  "team.user_created": "Створено працівника",
  "team.user_updated": "Оновлено працівника",
  "team.user_role_changed": "Змінено роль працівника",
  "team.user_deactivated": "Деактивовано працівника",
  "team.user_reactivated": "Відновлено працівника",
  "settings.updated": "Оновлено налаштування",
  "settings.clinic_profile_updated": "Оновлено профіль кабінету",
  "settings.clinic_logo_updated": "Оновлено логотип",
  "settings.room_created": "Створено кабінет",
  "settings.room_updated": "Оновлено кабінет",
  "settings.room_deactivated": "Деактивовано кабінет",
  "settings.room_reactivated": "Відновлено кабінет",
  "settings.service_created": "Створено послугу",
  "settings.service_updated": "Оновлено послугу",
  "settings.service_deactivated": "Деактивовано послугу",
  "settings.service_reactivated": "Відновлено послугу",
  "settings.appointment_status_config_updated": "Оновлено статус запису",
  "settings.clinic_schedule_updated": "Оновлено графік клініки",
  "patients.patient_created": "Створено пацієнта",
  "patients.patient_updated": "Оновлено пацієнта",
  "medical.record_updated": "Оновлено медичну картку",
  "medical.visit_recommendation_created": "Створено рекомендацію",
  "medical.visit_recommendation_updated": "Оновлено рекомендацію",
  "work_items.work_item_created": "Створено справу",
  "work_items.work_item_updated": "Оновлено справу",
  "work_items.work_item_completed": "Завершено справу",
  "work_items.work_item_reopened": "Повторно відкрито справу",
  "scheduling.appointment_created": "Створено запис",
  "scheduling.appointment_updated": "Оновлено запис",
  "scheduling.appointment_rescheduled": "Перенесено запис",
  "scheduling.appointment_canceled": "Скасовано запис",
  "scheduling.appointment_status_changed": "Змінено статус запису",
  "visits.visit_started": "Розпочато прийом",
  "visits.visit_draft_saved": "Збережено чернетку прийому",
  "visits.visit_photo_added": "Додано фото прийому",
  "visits.visit_photo_deleted": "Видалено фото чернетки",
  "visits.visit_completed": "Завершено прийом",
  "inventory.material_created": "Створено матеріал",
  "inventory.material_updated": "Оновлено матеріал",
  "inventory.material_deactivated": "Деактивовано матеріал",
  "inventory.material_reactivated": "Відновлено матеріал",
  "inventory.supplier_created": "Створено постачальника",
  "inventory.supplier_updated": "Оновлено постачальника",
  "inventory.supplier_deactivated": "Деактивовано постачальника",
  "inventory.supplier_reactivated": "Відновлено постачальника",
  "inventory.receipt_posted": "Проведено надходження",
  "inventory.manual_writeoff_posted": "Проведено ручне списання",
  "inventory.stocktake_created": "Створено інвентаризацію",
  "inventory.stock_movement_posted": "Проведено складський рух",
  "inventory.stocktake_posted": "Проведено інвентаризацію",
  "billing.payment_posted": "Проведено оплату",
  "billing.refund_posted": "Проведено повернення",
  "cash.deposit_posted": "Внесено готівку",
  "cash.withdrawal_posted": "Вилучено готівку",
  "cash.shift_opened": "Відкрито касову зміну",
  "cash.shift_closed": "Закрито касову зміну",
};

const fieldLabels: Readonly<Record<string, string>> = {
  first_name: "Ім’я",
  last_name: "Прізвище",
  display_name: "Працівник",
  email: "Email",
  phone: "Телефон",
  contact_name: "Контактна особа",
  address: "Адреса",
  note: "Примітка",
  role: "Роль",
  is_active: "Активний статус",
  must_change_password: "Зміна пароля при вході",
  temporary_password_expires_at: "Строк тимчасового пароля",
  status: "Статус",
  starts_at: "Початок",
  ends_at: "Завершення",
  specialist_id: "Спеціаліст",
  room_id: "Кабінет",
  service_id: "Послуга",
  complaints: "Скарги",
  has_no_complaints: "Скарг немає",
  recommendation: "Рекомендація",
  amount_minor: "Сума",
  payment_method: "Спосіб оплати",
  actual_cash_minor: "Фактична готівка",
  discrepancy_minor: "Розбіжність",
  completed_at: "Час завершення",
  version: "Версія",
};

const roleLabels: Readonly<Record<string, string>> = {
  admin: "Адмін / власник",
  reception: "Ресепшн",
  podologist: "Подолог",
  system: "Система",
};

export function auditSectionLabel(section: string): string {
  return sectionLabelMap[section as AuditSection] ?? section;
}

export function auditActionLabel(action: string): string {
  return actionLabels[action] ?? action.split(".").at(-1)?.replaceAll("_", " ") ?? action;
}

export function auditFieldLabel(field: string): string {
  const fallback = field.replaceAll("_", " ");
  return fieldLabels[field] ?? `${fallback.charAt(0).toLocaleUpperCase("uk")}${fallback.slice(1)}`;
}

export function auditRoleLabel(role: string): string {
  return roleLabels[role] ?? role;
}

export function auditInitials(displayName: string): string {
  return displayName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toLocaleUpperCase("uk");
}

export function formatAuditDateTime(value: string): string {
  return new Intl.DateTimeFormat("uk-UA", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Europe/Kyiv",
  }).format(new Date(value));
}

export function formatAuditListTime(value: string): string {
  return new Intl.DateTimeFormat("uk-UA", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
    timeZone: "Europe/Kyiv",
  }).format(new Date(value));
}

export function formatAuditValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (value === "[REDACTED]") return "Приховано";
  if (typeof value === "boolean") return value ? "Так" : "Ні";
  if (typeof value === "number") return value.toLocaleString("uk-UA");
  if (typeof value === "string") return value === "" ? "Порожньо" : value;
  if (Array.isArray(value) && value.length === 0) return "Порожній список";
  if (typeof value === "object" && Object.keys(value).length === 0) return "Порожній об’єкт";
  return JSON.stringify(value, null, 2);
}

export function auditObjectLink(object: AuditEventDetail["object"]): string | null {
  const encodedId = encodeURIComponent(object.id);
  if (object.type === "patient") return `/patients/${encodedId}/overview`;
  if (object.type === "appointment") return `/calendar?appointment=${encodedId}`;
  if (object.type === "visit") return `/visits/${encodedId}`;
  if (object.type === "work_item") return `/work-items?item=${encodedId}`;
  if (object.type === "material") return `/inventory?material=${encodedId}`;
  if (object.type === "supplier") return "/inventory?section=suppliers";
  if (object.type === "cash_shift") return `/finance/shifts?shift=${encodedId}`;
  if (object.type === "payment") return `/finance?operation=PAYMENT:${encodedId}`;
  if (["clinic_profile", "room", "service", "appointment_status_config", "clinic_schedule"].includes(object.type)) return "/settings";
  return null;
}
