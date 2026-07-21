export type IconName =
  | "overview"
  | "calendar"
  | "patients"
  | "team"
  | "tasks"
  | "finance"
  | "inventory"
  | "analytics"
  | "bell"
  | "settings"
  | "code"
  | "search"
  | "plus"
  | "chevron"
  | "menu"
  | "refresh"
  | "lock"
  | "empty"
  | "warning"
  | "close"
  | "phone"
  | "check"
  | "flag"
  | "arrow-left";

const iconPaths: Record<IconName, React.ReactNode> = {
  overview: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="2" />
      <rect x="14" y="3" width="7" height="7" rx="2" />
      <rect x="3" y="14" width="7" height="7" rx="2" />
      <rect x="14" y="14" width="7" height="7" rx="2" />
    </>
  ),
  calendar: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="3" />
      <path d="M16 3v4M8 3v4M3 10h18" />
    </>
  ),
  patients: (
    <>
      <circle cx="9" cy="8" r="4" />
      <path d="M3 21v-2a6 6 0 0 1 12 0v2M16 11a4 4 0 0 1 5 4v2" />
    </>
  ),
  team: (
    <>
      <circle cx="9" cy="8" r="3.5" />
      <circle cx="17" cy="9" r="2.5" />
      <path d="M3 20v-1.5a6 6 0 0 1 12 0V20M14 14.5a5 5 0 0 1 7 4.5v1" />
    </>
  ),
  tasks: (
    <>
      <rect x="4" y="3" width="16" height="18" rx="3" />
      <path d="m8 9 1.5 1.5L12 8M8 15h8" />
    </>
  ),
  finance: (
    <>
      <rect x="3" y="5" width="18" height="15" rx="3" />
      <path d="M3 10h18M16 15h2" />
    </>
  ),
  inventory: (
    <>
      <path d="m4 7 8-4 8 4-8 4-8-4Z" />
      <path d="m4 7v10l8 4 8-4V7M12 11v10" />
    </>
  ),
  analytics: (
    <>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </>
  ),
  bell: (
    <>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
      <path d="M10 21h4" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
    </>
  ),
  code: <path d="m8 9-4 3 4 3M16 9l4 3-4 3M14 5l-4 14" />,
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-4-4" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  chevron: <path d="m9 18 6-6-6-6" />,
  menu: (
    <>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 6v5h-5" />
      <path d="M19 11a8 8 0 1 0 1 5" />
    </>
  ),
  lock: (
    <>
      <rect x="4" y="10" width="16" height="11" rx="3" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </>
  ),
  empty: (
    <>
      <path d="M4 7h16v13H4zM8 4h8" />
      <path d="M8 12h8" />
    </>
  ),
  warning: (
    <>
      <path d="M12 3 2.8 20h18.4L12 3Z" />
      <path d="M12 9v5M12 17h.01" />
    </>
  ),
  close: <path d="m6 6 12 12M18 6 6 18" />,
  phone: <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 2 .7 2.8a2 2 0 0 1-.4 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2Z" />,
  check: <path d="m5 12 4 4L19 6" />,
  flag: <path d="M5 21V4m0 0h10l-1 4 1 4H5" />,
  "arrow-left": <path d="m15 18-6-6 6-6" />,
};

interface IconProps {
  readonly name: IconName;
  readonly className?: string | undefined;
}

export function Icon({ name, className }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      focusable="false"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
    >
      {iconPaths[name]}
    </svg>
  );
}
