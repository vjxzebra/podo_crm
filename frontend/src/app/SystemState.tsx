import { Link } from "react-router";

import { Icon, type IconName } from "./Icon";

export type SystemStateKind =
  | "loading"
  | "empty"
  | "error"
  | "forbidden"
  | "not-found"
  | "anonymous";

interface StateCopy {
  readonly eyebrow: string;
  readonly title: string;
  readonly description: string;
  readonly icon: IconName;
  readonly action: string;
}

const stateCopy: Record<SystemStateKind, StateCopy> = {
  loading: {
    eyebrow: "Завантаження",
    title: "Готуємо робочий простір",
    description: "Перевіряємо сесію та отримуємо актуальні дані. Це може тривати кілька секунд.",
    icon: "refresh",
    action: "Повернутися до огляду",
  },
  empty: {
    eyebrow: "Поки порожньо",
    title: "Тут ще немає даних",
    description: "Коли з’являться записи, вони відобразяться тут із доступними діями.",
    icon: "empty",
    action: "Повернутися до огляду",
  },
  error: {
    eyebrow: "Помилка",
    title: "Не вдалося завантажити дані",
    description: "Збережіть контекст роботи та спробуйте ще раз. Якщо проблема повториться, зверніться до адміністратора.",
    icon: "warning",
    action: "Спробувати ще раз",
  },
  forbidden: {
    eyebrow: "403 · Немає доступу",
    title: "Цей розділ недоступний",
    description: "Серверна сесія не дозволяє переглядати цей ресурс. Навігація в React не є перевіркою доступу.",
    icon: "lock",
    action: "Повернутися до огляду",
  },
  "not-found": {
    eyebrow: "404 · Не знайдено",
    title: "Такої сторінки немає",
    description: "Адреса могла змінитися або посилання більше не актуальне.",
    icon: "search",
    action: "Повернутися до огляду",
  },
  anonymous: {
    eyebrow: "Потрібна сесія",
    title: "Увійдіть, щоб продовжити",
    description: "Екран входу й реальна серверна сесія будуть підключені в TP-201.",
    icon: "lock",
    action: "Повернутися до огляду",
  },
};

interface SystemStateProps {
  readonly kind: SystemStateKind;
  readonly compact?: boolean;
  readonly onAction?: (() => void) | undefined;
}

export function SystemState({ kind, compact = false, onAction }: SystemStateProps) {
  const copy = stateCopy[kind];
  const isLoading = kind === "loading";

  return (
    <section
      aria-busy={isLoading || undefined}
      aria-live={isLoading ? "polite" : undefined}
      className={`system-state system-state--${kind}${compact ? " system-state--compact" : ""}`}
      data-testid={`state-${kind}`}
    >
      <span className="system-state__halo" aria-hidden="true">
        <Icon className={isLoading ? "system-state__spinner" : undefined} name={copy.icon} />
      </span>
      <p className="eyebrow">{copy.eyebrow}</p>
      <h1>{copy.title}</h1>
      <p className="system-state__description">{copy.description}</p>
      {isLoading ? (
        <div className="loading-lines" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      ) : onAction === undefined ? (
        <Link className="button button--primary" to="/">
          <Icon name={kind === "error" ? "refresh" : "arrow-left"} />
          {copy.action}
        </Link>
      ) : (
        <button className="button button--primary" onClick={onAction} type="button">
          <Icon name="refresh" />
          {copy.action}
        </button>
      )}
    </section>
  );
}
