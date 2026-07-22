import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type DragEvent,
  type RefObject,
} from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders } from "../auth/AuthContext";

export type VisitPhoto = components["schemas"]["VisitPhoto"];
type VisitPhotoKind = components["schemas"]["VisitPhotoKindEnum"];
type UploadPhase = "idle" | "intent" | "uploading" | "error";

type UploadState = Readonly<{
  phase: UploadPhase;
  progress: number;
  message: string | null;
  file: File | null;
  intentId: string | null;
}>;

type VisitPhotosStepProps = Readonly<{
  visitId: string;
  photos: readonly VisitPhoto[];
  editable: boolean;
  onPhotosChange: (photos: readonly VisitPhoto[]) => void;
}>;

const MAX_PHOTO_BYTES = 10 * 1024 * 1024;
const ALLOWED_PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
const EMPTY_UPLOAD: UploadState = {
  phase: "idle",
  progress: 0,
  message: null,
  file: null,
  intentId: null,
};

const photoDateFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: "Europe/Kyiv",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function fileSizeLabel(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024)).toLocaleString("uk-UA")} КБ`;
  return `${(bytes / (1024 * 1024)).toLocaleString("uk-UA", { maximumFractionDigits: 1 })} МБ`;
}

function sortPhotos(photos: readonly VisitPhoto[]): readonly VisitPhoto[] {
  return [...photos].sort((left, right) => {
    if (left.kind !== right.kind) return left.kind === "BEFORE" ? -1 : 1;
    return left.created_at.localeCompare(right.created_at);
  });
}

export function VisitPhotosStep({
  visitId,
  photos,
  editable,
  onPhotosChange,
}: VisitPhotosStepProps) {
  const beforeInput = useRef<HTMLInputElement>(null);
  const afterInput = useRef<HTMLInputElement>(null);
  const [uploads, setUploads] = useState<Record<VisitPhotoKind, UploadState>>({
    BEFORE: EMPTY_UPLOAD,
    AFTER: EMPTY_UPLOAD,
  });
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [viewerPhotoId, setViewerPhotoId] = useState<string | null>(null);
  const viewerDialogRef = useRef<HTMLElement>(null);
  const viewerCloseRef = useRef<HTMLButtonElement>(null);
  const viewerTriggerRef = useRef<HTMLButtonElement | null>(null);
  const orderedPhotos = useMemo(() => sortPhotos(photos), [photos]);
  const viewerPhotoIndex = viewerPhotoId === null
    ? -1
    : orderedPhotos.findIndex((photo) => photo.id === viewerPhotoId);
  const viewerPhoto = viewerPhotoIndex === -1 ? null : (orderedPhotos[viewerPhotoIndex] ?? null);
  const viewerOpen = viewerPhoto !== null;

  const closeViewer = useCallback(() => {
    const trigger = viewerTriggerRef.current;
    setViewerPhotoId(null);
    window.setTimeout(() => { trigger?.focus(); }, 0);
  }, []);

  const moveViewer = useCallback((offset: -1 | 1) => {
    setViewerPhotoId((currentId) => {
      if (currentId === null || orderedPhotos.length < 2) return currentId;
      const currentIndex = orderedPhotos.findIndex((photo) => photo.id === currentId);
      if (currentIndex === -1) return orderedPhotos[0]?.id ?? null;
      const nextIndex = (currentIndex + offset + orderedPhotos.length) % orderedPhotos.length;
      return orderedPhotos[nextIndex]?.id ?? currentId;
    });
  }, [orderedPhotos]);

  useEffect(() => {
    if (!viewerOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    viewerCloseRef.current?.focus();
    return () => { document.body.style.overflow = previousOverflow; };
  }, [viewerOpen]);

  useEffect(() => {
    if (!viewerOpen) return undefined;
    const handleViewerKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeViewer();
        return;
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        moveViewer(-1);
        return;
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        moveViewer(1);
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = viewerDialogRef.current?.querySelectorAll<HTMLButtonElement>(
        "button:not(:disabled)",
      );
      if (focusable === undefined || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", handleViewerKeyDown);
    return () => { document.removeEventListener("keydown", handleViewerKeyDown); };
  }, [closeViewer, moveViewer, viewerOpen]);

  useEffect(() => {
    if (viewerPhotoId !== null && viewerPhoto === null) closeViewer();
  }, [closeViewer, viewerPhoto, viewerPhotoId]);

  const replaceUpload = (kind: VisitPhotoKind, value: UploadState) => {
    setUploads((current) => ({ ...current, [kind]: value }));
  };

  const uploadPhoto = async (
    kind: VisitPhotoKind,
    file: File,
    existingIntentId: string | null = null,
  ) => {
    if (!editable) return;
    if (!ALLOWED_PHOTO_TYPES.includes(file.type as (typeof ALLOWED_PHOTO_TYPES)[number])) {
      replaceUpload(kind, {
        phase: "error",
        progress: 0,
        message: "Оберіть JPEG, PNG або WebP. HEIC/HEIF у поточній версії не підтримується.",
        file: null,
        intentId: null,
      });
      return;
    }
    if (file.size > MAX_PHOTO_BYTES) {
      replaceUpload(kind, {
        phase: "error",
        progress: 0,
        message: "Фото завелике. Максимальний розмір одного файла — 10 МБ.",
        file: null,
        intentId: null,
      });
      return;
    }

    let intentId = existingIntentId;
    if (intentId === null) {
      replaceUpload(kind, {
        phase: "intent",
        progress: 20,
        message: `Готуємо приватне завантаження для ${file.name}…`,
        file,
        intentId: null,
      });
      const intentResult = await apiClient.POST(
        "/api/v1/visits/{visit_id}/photos/upload-intents",
        {
          params: { path: { visit_id: visitId } },
          body: { kind },
          headers: csrfHeaders(),
        },
      ).catch(() => null);
      if (intentResult === null) {
        replaceUpload(kind, {
          phase: "error",
          progress: 0,
          message: "Немає зв’язку із сервером. Фото не передано — повторіть спробу.",
          file,
          intentId: null,
        });
        return;
      }
      if (intentResult.data === undefined) {
        replaceUpload(kind, {
          phase: "error",
          progress: 0,
          message: intentResult.error.message,
          file,
          intentId: null,
        });
        return;
      }
      intentId = intentResult.data.id;
    }

    replaceUpload(kind, {
      phase: "uploading",
      progress: 70,
      message: `Завантажуємо й очищуємо метадані ${file.name}…`,
      file,
      intentId,
    });
    const finalizeResult = await apiClient.POST("/api/v1/visits/{visit_id}/photos", {
      params: { path: { visit_id: visitId } },
      body: { intent_id: intentId, photo: file.name },
      bodySerializer: () => {
        const body = new FormData();
        body.append("intent_id", intentId);
        body.append("photo", file, file.name);
        return body;
      },
      headers: csrfHeaders(),
    }).catch(() => null);
    if (finalizeResult === null) {
      replaceUpload(kind, {
        phase: "error",
        progress: 0,
        message: "Відповідь сервера втрачено. Безпечний повтор не створить дубль.",
        file,
        intentId,
      });
      return;
    }
    if (finalizeResult.data === undefined) {
      const expired = finalizeResult.error.code === "visit_photo_intent_expired";
      replaceUpload(kind, {
        phase: "error",
        progress: 0,
        message: finalizeResult.error.message,
        file,
        intentId: expired ? null : intentId,
      });
      return;
    }
    onPhotosChange(sortPhotos([
      ...photos.filter((photo) => photo.id !== finalizeResult.data.id),
      finalizeResult.data,
    ]));
    replaceUpload(kind, {
      phase: "idle",
      progress: 100,
      message: `Фото ${file.name} додано до приватної чернетки.`,
      file: null,
      intentId: null,
    });
  };

  const deletePhoto = async (photo: VisitPhoto) => {
    setDeletingId(photo.id);
    setDeleteError(null);
    const result = await apiClient.DELETE(
      "/api/v1/visits/{visit_id}/photos/{photo_id}",
      {
        params: { path: { visit_id: visitId, photo_id: photo.id } },
        headers: csrfHeaders(),
      },
    ).catch(() => null);
    setDeletingId(null);
    if (result === null) {
      setDeleteError("Немає зв’язку із сервером. Фото лишилося у прийомі.");
      return;
    }
    if (!result.response.ok) {
      setDeleteError(result.error?.message ?? "Не вдалося видалити фото.");
      return;
    }
    setConfirmDeleteId(null);
    onPhotosChange(photos.filter((item) => item.id !== photo.id));
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>, kind: VisitPhotoKind) => {
    event.preventDefault();
    const file = event.dataTransfer.files[0];
    if (file !== undefined) void uploadPhoto(kind, file);
  };

  const renderBlock = (
    kind: VisitPhotoKind,
    title: string,
    buttonLabel: string,
    inputRef: RefObject<HTMLInputElement | null>,
  ) => {
    const kindPhotos = photos.filter((photo) => photo.kind === kind);
    const upload = uploads[kind];
    const retryFile = upload.file;
    const busy = upload.phase === "intent" || upload.phase === "uploading";
    const inputId = `visit-photo-${kind.toLowerCase()}`;
    return (
      <section className="visit-photo-block" aria-labelledby={`${inputId}-title`}>
        <header>
          <div>
            <p className="eyebrow">{kind === "BEFORE" ? "BEFORE" : "AFTER"}</p>
            <h3 id={`${inputId}-title`}>{title}</h3>
            <p>{kindPhotos.length} із 10 фото · приватний доступ</p>
          </div>
          <span className="visit-photo-count">{kindPhotos.length}/10</span>
        </header>

        <div
          className={`visit-photo-dropzone${busy ? " visit-photo-dropzone--busy" : ""}`}
          onDragOver={(event) => { if (editable) event.preventDefault(); }}
          onDrop={(event) => { handleDrop(event, kind); }}
        >
          <span className="visit-photo-dropzone__icon"><Icon name="photo" /></span>
          <div><strong>Перетягніть фото сюди</strong><small>JPEG, PNG або WebP · до 10 МБ</small></div>
          <button
            className="button button--secondary"
            disabled={!editable || busy || kindPhotos.length >= 10}
            onClick={() => { inputRef.current?.click(); }}
            type="button"
          ><Icon name="plus" />{buttonLabel}</button>
          <input
            accept={ALLOWED_PHOTO_TYPES.join(",")}
            aria-label={`Файл для блоку «${title}»`}
            className="sr-only"
            id={inputId}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file !== undefined) void uploadPhoto(kind, file);
              event.currentTarget.value = "";
            }}
            ref={inputRef}
            type="file"
          />
        </div>

        {upload.message === null ? null : (
          <div
            aria-live="polite"
            className={`visit-photo-upload-state${upload.phase === "error" ? " visit-photo-upload-state--error" : ""}`}
            role={upload.phase === "error" ? "alert" : "status"}
          >
            {busy ? <progress aria-label={`Прогрес завантаження у блок «${title}»`} max={100} value={upload.progress} /> : null}
            <span>{upload.message}</span>
            {upload.phase === "error" && retryFile !== null ? (
              <button className="text-action" onClick={() => { void uploadPhoto(kind, retryFile, upload.intentId); }} type="button"><Icon name="refresh" />Повторити</button>
            ) : null}
          </div>
        )}

        {kindPhotos.length === 0 ? (
          <div className="visit-photo-empty"><Icon name="photo" /><span><strong>Фото ще не додані</strong><small>Вони зберігатимуться лише в цьому відвідуванні.</small></span></div>
        ) : (
          <div className="visit-photo-grid">
            {kindPhotos.map((photo, index) => (
              <article className="visit-photo-card" key={photo.id}>
                <button
                  aria-haspopup="dialog"
                  aria-label={`Відкрити ${title.toLowerCase()} ${String(index + 1)}: ${photo.original_name} у слайдері`}
                  className="visit-photo-preview"
                  onClick={(event) => {
                    viewerTriggerRef.current = event.currentTarget;
                    setViewerPhotoId(photo.id);
                  }}
                  type="button"
                >
                  <img
                    alt={`${title}, фото ${String(index + 1)}`}
                    loading="lazy"
                    src={photo.preview_url ?? photo.image_url}
                  />
                  {photo.preview_status === "PROCESSING" ? <span>Готуємо мініатюру…</span> : null}
                  {photo.preview_status === "FAILED" ? <span>Показано захищений оригінал</span> : null}
                </button>
                <div className="visit-photo-card__meta">
                  <strong title={photo.original_name}>{photo.original_name}</strong>
                  <small>{fileSizeLabel(photo.size)} · {photo.width}×{photo.height}</small>
                  <small>{photoDateFormatter.format(new Date(photo.created_at))}</small>
                </div>
                {confirmDeleteId === photo.id ? (
                  <div className="visit-photo-delete-confirm" role="alert">
                    <span>Видалити фото з чернетки?</span>
                    <div>
                      <button className="button button--secondary" disabled={deletingId === photo.id} onClick={() => { setConfirmDeleteId(null); }} type="button">Скасувати</button>
                      <button className="button button--danger" disabled={deletingId === photo.id} onClick={() => { void deletePhoto(photo); }} type="button">{deletingId === photo.id ? "Видаляємо…" : "Так, видалити"}</button>
                    </div>
                  </div>
                ) : (
                  <button
                    aria-label={`Видалити фото ${photo.original_name}`}
                    className="button button--danger-ghost"
                    disabled={!editable || deletingId !== null}
                    onClick={() => { setConfirmDeleteId(photo.id); setDeleteError(null); }}
                    type="button"
                  >Видалити</button>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    );
  };

  return (
    <div className="visit-photos-step">
      {deleteError ? <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{deleteError}</span></div> : null}
      <div className="visit-photo-blocks">
        {renderBlock("BEFORE", "До процедури", "Додати фото ДО", beforeInput)}
        {renderBlock("AFTER", "Після процедури", "Додати фото ПІСЛЯ", afterInput)}
      </div>
      <aside className="visit-photo-privacy"><Icon name="lock" /><span><strong>Приватні медичні дані</strong><small>Фото доступні лише адміністратору та відповідальному подологу. Метадані камери й GPS видаляються перед збереженням.</small></span></aside>
      {viewerPhoto === null ? null : (
        <div
          className="modal-layer visit-photo-lightbox"
          onMouseDown={(event) => { if (event.currentTarget === event.target) closeViewer(); }}
          role="presentation"
        >
          <section
            aria-describedby="visit-photo-slider-caption"
            aria-labelledby="visit-photo-slider-title"
            aria-modal="true"
            className="visit-photo-lightbox__dialog"
            ref={viewerDialogRef}
            role="dialog"
          >
            <header className="visit-photo-lightbox__header">
              <div>
                <span>{viewerPhoto.kind === "BEFORE" ? "BEFORE · До процедури" : "AFTER · Після процедури"}</span>
                <h2 id="visit-photo-slider-title">Перегляд фото</h2>
              </div>
              <button
                aria-label="Закрити перегляд фото"
                className="visit-photo-lightbox__close"
                onClick={closeViewer}
                ref={viewerCloseRef}
                type="button"
              ><Icon name="close" /></button>
            </header>
            <div className="visit-photo-lightbox__stage">
              <button
                aria-label="Попереднє фото"
                className="visit-photo-lightbox__arrow visit-photo-lightbox__arrow--previous"
                disabled={orderedPhotos.length < 2}
                onClick={() => { moveViewer(-1); }}
                type="button"
              ><Icon name="arrow-left" /></button>
              <img
                alt={`${viewerPhoto.kind === "BEFORE" ? "До процедури" : "Після процедури"}: ${viewerPhoto.original_name}`}
                key={viewerPhoto.id}
                src={viewerPhoto.image_url}
              />
              <button
                aria-label="Наступне фото"
                className="visit-photo-lightbox__arrow visit-photo-lightbox__arrow--next"
                disabled={orderedPhotos.length < 2}
                onClick={() => { moveViewer(1); }}
                type="button"
              ><Icon name="chevron" /></button>
            </div>
            <footer className="visit-photo-lightbox__footer" id="visit-photo-slider-caption">
              <div aria-live="polite">
                <strong>{viewerPhoto.original_name}</strong>
                <span>{fileSizeLabel(viewerPhoto.size)} · {viewerPhoto.width}×{viewerPhoto.height}</span>
              </div>
              <b>{viewerPhotoIndex + 1} із {orderedPhotos.length}</b>
            </footer>
          </section>
        </div>
      )}
    </div>
  );
}
