import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { formatPatientVisitDate } from "./PatientVisitHistoryTab";

type VisitPhoto = components["schemas"]["VisitPhoto"];
type VisitPhotoKind = components["schemas"]["VisitPhotoKindEnum"];
type PhotoArchiveVisit = components["schemas"]["PatientPhotoArchiveVisit"];

interface ViewerState {
  readonly visitId: string;
  readonly kind: VisitPhotoKind;
  readonly photoId: string;
}

const photoCreatedFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: "Europe/Kyiv",
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function kindLabel(kind: VisitPhotoKind): string {
  return kind === "BEFORE" ? "До процедури" : "Після процедури";
}

function sortedPhotos(photos: readonly VisitPhoto[], kind: VisitPhotoKind): readonly VisitPhoto[] {
  return [...photos
    .filter((photo) => photo.kind === kind)
  ].sort((left, right) => left.created_at.localeCompare(right.created_at));
}

function visitCaption(visit: PhotoArchiveVisit): string {
  return visit.services.map((service) => service.service_name).join(" · ") || visit.public_number;
}

function ArchiveLoading() {
  return (
    <div aria-label="Завантаження архіву фото" className="patient-photo-archive-loading" role="status">
      <span />
      <span />
    </div>
  );
}

export function PatientPhotoArchiveTab({ patientId }: { readonly patientId: string }) {
  const [visits, setVisits] = useState<readonly PhotoArchiveVisit[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isRefreshingImage, setIsRefreshingImage] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewer, setViewer] = useState<ViewerState | null>(null);
  const [imageError, setImageError] = useState(false);
  const [failedPreviews, setFailedPreviews] = useState<ReadonlySet<string>>(new Set());
  const dialogRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const load = useCallback(async (cursor: string | null = null) => {
    if (cursor === null) setIsLoading(true);
    else setIsLoadingMore(true);
    setError(null);
    const result = await apiClient.GET("/api/v1/patients/{patient_id}/photos", {
      params: {
        path: { patient_id: patientId },
        ...(cursor === null ? {} : { query: { cursor } }),
      },
    }).catch(() => null);
    setIsLoading(false);
    setIsLoadingMore(false);
    if (result === null) {
      setError("Немає зв’язку із сервером. Приватні фото не завантажено.");
      return;
    }
    if (result.data === undefined) {
      setError(result.error.message);
      return;
    }
    const page = result.data.visits;
    setVisits((current) => cursor === null ? page : [...current, ...page]);
    setNextCursor(result.data.next_cursor);
  }, [patientId]);

  useEffect(() => {
    void load();
  }, [load]);

  const viewerVisit = useMemo(
    () => viewer === null ? null : (visits.find((visit) => visit.id === viewer.visitId) ?? null),
    [viewer, visits],
  );
  const viewerPhotos = useMemo(
    () => viewer === null || viewerVisit === null ? [] : sortedPhotos(viewerVisit.photos, viewer.kind),
    [viewer, viewerVisit],
  );
  const viewerPhotoIndex = viewer === null
    ? -1
    : viewerPhotos.findIndex((photo) => photo.id === viewer.photoId);
  const viewerPhoto = viewerPhotoIndex < 0 ? null : (viewerPhotos[viewerPhotoIndex] ?? null);
  const viewerOpen = viewer !== null;

  const closeViewer = useCallback(() => {
    const trigger = triggerRef.current;
    setViewer(null);
    setImageError(false);
    window.setTimeout(() => { trigger?.focus(); }, 0);
  }, []);

  const moveViewer = useCallback((offset: -1 | 1) => {
    setViewer((current) => {
      if (current === null || viewerPhotos.length < 2) return current;
      const currentIndex = viewerPhotos.findIndex((photo) => photo.id === current.photoId);
      const nextIndex = (currentIndex + offset + viewerPhotos.length) % viewerPhotos.length;
      const nextPhoto = viewerPhotos[nextIndex];
      return nextPhoto === undefined ? current : { ...current, photoId: nextPhoto.id };
    });
    setImageError(false);
  }, [viewerPhotos]);

  const selectKind = useCallback((kind: VisitPhotoKind) => {
    setViewer((current) => {
      if (current === null || viewerVisit === null) return current;
      const first = sortedPhotos(viewerVisit.photos, kind)[0];
      return first === undefined ? current : { ...current, kind, photoId: first.id };
    });
    setImageError(false);
  }, [viewerVisit]);

  useEffect(() => {
    if (!viewerOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    return () => { document.body.style.overflow = previousOverflow; };
  }, [viewerOpen]);

  useEffect(() => {
    if (viewer === null) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target instanceof HTMLElement ? event.target : null;
      const targetIsTab = target?.getAttribute("role") === "tab";
      if (event.key === "Escape") {
        event.preventDefault();
        closeViewer();
        return;
      }
      if ((event.key === "ArrowLeft" || event.key === "ArrowRight") && targetIsTab) {
        event.preventDefault();
        const nextKind = viewer.kind === "BEFORE" ? "AFTER" : "BEFORE";
        if (viewerVisit !== null && sortedPhotos(viewerVisit.photos, nextKind).length > 0) {
          selectKind(nextKind);
          window.setTimeout(() => {
            dialogRef.current?.querySelector<HTMLButtonElement>(`[role="tab"][data-kind="${nextKind}"]`)?.focus();
          }, 0);
        }
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
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        "button:not(:disabled), [href], [tabindex]:not([tabindex='-1'])",
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
    document.addEventListener("keydown", onKeyDown);
    return () => { document.removeEventListener("keydown", onKeyDown); };
  }, [closeViewer, moveViewer, selectKind, viewer, viewerVisit]);

  useEffect(() => {
    if (viewer !== null && (viewerVisit === null || viewerPhoto === null)) closeViewer();
  }, [closeViewer, viewer, viewerPhoto, viewerVisit]);

  const focusKindTab = (kind: VisitPhotoKind) => {
    window.setTimeout(() => {
      dialogRef.current?.querySelector<HTMLButtonElement>(`[role="tab"][data-kind="${kind}"]`)?.focus();
    }, 0);
  };

  const handleTabKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (event.key === "Home") {
      event.preventDefault();
      const kind = viewerVisit !== null && sortedPhotos(viewerVisit.photos, "BEFORE").length > 0
        ? "BEFORE"
        : "AFTER";
      selectKind(kind);
      focusKindTab(kind);
    } else if (event.key === "End") {
      event.preventDefault();
      const kind = viewerVisit !== null && sortedPhotos(viewerVisit.photos, "AFTER").length > 0
        ? "AFTER"
        : "BEFORE";
      selectKind(kind);
      focusKindTab(kind);
    }
  };

  const refreshViewerPhoto = async () => {
    if (viewer === null || viewerPhoto === null) return;
    setIsRefreshingImage(true);
    const result = await apiClient.GET("/api/v1/visits/{visit_id}/photos/{photo_id}", {
      params: {
        path: { visit_id: viewer.visitId, photo_id: viewerPhoto.id },
      },
    }).catch(() => null);
    setIsRefreshingImage(false);
    if (result?.data === undefined) return;
    setVisits((current) => current.map((visit) => visit.id !== viewer.visitId ? visit : {
      ...visit,
      photos: visit.photos.map((photo) => photo.id === result.data.id ? result.data : photo),
    }));
    setImageError(false);
    setFailedPreviews((current) => {
      const next = new Set(current);
      next.delete(result.data.id);
      return next;
    });
    window.setTimeout(() => { closeRef.current?.focus(); }, 0);
  };

  return (
    <section className="surface patient-archive patient-photo-archive" aria-labelledby="patient-photos-title">
      <header className="patient-archive__header">
        <div>
          <p className="eyebrow">Приватні медичні матеріали</p>
          <h2 id="patient-photos-title">Фото до / після</h2>
          <p>Фото згруповані за завершеними відвідуваннями та відкриваються лише через короткоживучі захищені посилання.</p>
        </div>
        <span className="patient-privacy-badge"><Icon name="lock" />Медичний доступ</span>
      </header>

      {isLoading ? <ArchiveLoading /> : null}
      {!isLoading && error !== null && visits.length === 0 ? (
        <div className="patient-archive-state" role="alert">
          <Icon name="warning" />
          <div><strong>Не вдалося завантажити фото</strong><p>{error}</p></div>
          <button className="button button--secondary" onClick={() => { void load(); }} type="button"><Icon name="refresh" />Повторити</button>
        </div>
      ) : null}
      {!isLoading && error === null && visits.length === 0 ? (
        <div className="patient-archive-state patient-archive-state--empty">
          <Icon name="photo" />
          <div><strong>Фото «до / після» ще немає</strong><p>Архів поповниться після завершення візиту з доданими фото.</p></div>
        </div>
      ) : null}

      {visits.length > 0 ? (
        <div className="patient-photo-visits">
          {visits.map((visit) => (
            <article className="patient-photo-visit" key={visit.id}>
              <header>
                <div><time dateTime={visit.occurred_at}>{formatPatientVisitDate(visit.occurred_at)}</time><h3>{visitCaption(visit)}</h3><p>{visit.public_number} · {visit.specialist.display_name}</p></div>
                <span>{visit.photos.length} фото</span>
              </header>
              <div className="patient-photo-kinds">
                {(["BEFORE", "AFTER"] as const).map((kind) => {
                  const photos = sortedPhotos(visit.photos, kind);
                  return (
                    <section aria-label={kindLabel(kind)} className="patient-photo-kind" key={kind}>
                      <div className="patient-photo-kind__title"><span>{kind}</span><strong>{kindLabel(kind)}</strong><b>{photos.length}</b></div>
                      {photos.length === 0 ? <div className="patient-photo-kind__empty"><Icon name="photo" />Немає фото</div> : (
                        <div className="patient-photo-thumbnails">
                          {photos.map((photo, index) => {
                            const failed = failedPreviews.has(photo.id);
                            return (
                              <button
                                aria-haspopup="dialog"
                                aria-label={`Відкрити «${kindLabel(kind)}», фото ${String(index + 1)} у слайдері`}
                                className="patient-photo-thumbnail"
                                key={photo.id}
                                onClick={(event) => {
                                  triggerRef.current = event.currentTarget;
                                  setViewer({ visitId: visit.id, kind, photoId: photo.id });
                                  setImageError(false);
                                }}
                                type="button"
                              >
                                {failed ? <span><Icon name="warning" />Фото тимчасово недоступне</span> : (
                                  <img
                                    alt=""
                                    loading="lazy"
                                    onError={() => { setFailedPreviews((current) => new Set(current).add(photo.id)); }}
                                    src={photo.preview_url ?? photo.image_url}
                                  />
                                )}
                                <small>{index + 1}</small>
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </section>
                  );
                })}
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {error !== null && visits.length > 0 ? <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div> : null}
      {nextCursor === null ? null : <div className="patient-archive__more"><button className="button button--secondary" disabled={isLoadingMore} onClick={() => { void load(nextCursor); }} type="button">{isLoadingMore ? "Завантажуємо…" : "Показати попередні відвідування"}</button></div>}

      {viewer === null || viewerVisit === null || viewerPhoto === null ? null : (
        <div className="modal-layer patient-photo-viewer" onMouseDown={(event) => { if (event.currentTarget === event.target) closeViewer(); }} role="presentation">
          <section
            aria-describedby="patient-photo-viewer-caption"
            aria-labelledby="patient-photo-viewer-title"
            aria-modal="true"
            className="patient-photo-viewer__dialog"
            ref={dialogRef}
            role="dialog"
          >
            <header className="patient-photo-viewer__header">
              <div><span>{viewerVisit.public_number} · {formatPatientVisitDate(viewerVisit.occurred_at)}</span><h2 id="patient-photo-viewer-title">{visitCaption(viewerVisit)}</h2></div>
              <button aria-label="Закрити перегляд фото" className="patient-photo-viewer__close" onClick={closeViewer} ref={closeRef} type="button"><Icon name="close" /></button>
            </header>
            <div aria-label="Група фото" className="patient-photo-viewer__tabs" role="tablist">
              {(["BEFORE", "AFTER"] as const).map((kind) => {
                const count = sortedPhotos(viewerVisit.photos, kind).length;
                return (
                  <button
                    aria-label={`${kindLabel(kind)}, ${String(count)} фото`}
                    aria-controls="patient-photo-active-panel"
                    aria-selected={viewer.kind === kind}
                    data-kind={kind}
                    disabled={count === 0}
                    id={`patient-photo-tab-${kind.toLowerCase()}`}
                    key={kind}
                    onClick={() => { selectKind(kind); }}
                    onKeyDown={handleTabKeyDown}
                    role="tab"
                    tabIndex={viewer.kind === kind ? 0 : -1}
                    type="button"
                  ><span>{kindLabel(kind)}</span><b>{count}</b></button>
                );
              })}
            </div>
            <div aria-labelledby={`patient-photo-tab-${viewer.kind.toLowerCase()}`} className="patient-photo-viewer__panel" id="patient-photo-active-panel" role="tabpanel">
              <p aria-live="polite" className="sr-only" role="status">{kindLabel(viewer.kind)}, фото {viewerPhotoIndex + 1} із {viewerPhotos.length}: {viewerPhoto.original_name}</p>
              <div className="patient-photo-viewer__stage">
                <button aria-label="Попереднє фото" className="patient-photo-viewer__arrow patient-photo-viewer__arrow--previous" disabled={viewerPhotos.length < 2} onClick={() => { moveViewer(-1); }} type="button"><Icon name="arrow-left" /></button>
                {imageError ? (
                  <div className="patient-photo-viewer__image-error" role="alert"><Icon name="warning" /><strong>Фото не завантажилося</strong><p>Захищене посилання могло завершити дію.</p><button className="button button--secondary" disabled={isRefreshingImage} onClick={() => { void refreshViewerPhoto(); }} type="button"><Icon name="refresh" />{isRefreshingImage ? "Оновлюємо…" : "Оновити посилання"}</button></div>
                ) : <img alt={`${kindLabel(viewer.kind)}: ${viewerPhoto.original_name}`} key={`${viewerPhoto.id}-${viewerPhoto.image_url}`} onError={() => { setImageError(true); }} src={viewerPhoto.image_url} />}
                <button aria-label="Наступне фото" className="patient-photo-viewer__arrow patient-photo-viewer__arrow--next" disabled={viewerPhotos.length < 2} onClick={() => { moveViewer(1); }} type="button"><Icon name="chevron" /></button>
              </div>
              <div aria-label="Мініатюри поточної групи" className="patient-photo-viewer__thumbs">
                {viewerPhotos.map((photo, index) => (
                  <button aria-current={photo.id === viewerPhoto.id ? "true" : undefined} aria-label={`Показати фото ${String(index + 1)}`} key={photo.id} onClick={() => { setViewer({ ...viewer, photoId: photo.id }); setImageError(false); }} type="button"><img alt="" src={photo.preview_url ?? photo.image_url} /><span>{index + 1}</span></button>
                ))}
              </div>
            </div>
            <footer className="patient-photo-viewer__footer" id="patient-photo-viewer-caption">
              <div><strong>{viewerPhoto.original_name}</strong><span>{photoCreatedFormatter.format(new Date(viewerPhoto.created_at))} · {viewerPhoto.created_by_name}</span></div>
              <b>{viewerPhotoIndex + 1} із {viewerPhotos.length}</b>
            </footer>
          </section>
        </div>
      )}
    </section>
  );
}
