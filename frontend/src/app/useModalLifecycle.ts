import { useEffect, useRef, type RefObject } from "react";

const focusableSelector = [
  "button:not(:disabled)",
  "input:not(:disabled)",
  "[href]:not([tabindex='-1'])",
  "[tabindex]:not([tabindex='-1'])",
].join(", ");

export function useModalLifecycle({
  dialogRef,
  initialFocusRef,
  isOpen = true,
  onEscape,
}: {
  readonly dialogRef: RefObject<HTMLElement | null>;
  readonly initialFocusRef: RefObject<HTMLElement | null>;
  readonly isOpen?: boolean;
  readonly onEscape: () => void;
}) {
  const escapeRef = useRef(onEscape);

  useEffect(() => {
    escapeRef.current = onEscape;
  }, [onEscape]);

  useEffect(() => {
    if (!isOpen) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.setTimeout(() => {
      (initialFocusRef.current ?? dialogRef.current)?.focus();
    }, 0);

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        escapeRef.current();
        return;
      }
      if (event.key !== "Tab") return;

      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(focusableSelector);
      if (focusable === undefined || focusable.length === 0) {
        event.preventDefault();
        dialogRef.current?.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!dialogRef.current?.contains(document.activeElement)) {
        event.preventDefault();
        (event.shiftKey ? last : first)?.focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [dialogRef, initialFocusRef, isOpen]);
}
