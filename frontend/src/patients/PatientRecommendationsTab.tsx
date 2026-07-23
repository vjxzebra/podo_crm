import { useCallback, useEffect, useMemo, useRef, useState, type SyntheticEvent } from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders } from "../auth/AuthContext";
import { formatPatientVisitDate } from "./PatientVisitHistoryTab";

type PatientRecommendation = components["schemas"]["PatientRecommendation"];
type RecommendationVisit = components["schemas"]["RecommendationVisitSummary"];
type RecommendationResponse = components["schemas"]["PatientRecommendationResponse"];
type VisitRecommendation = components["schemas"]["VisitRecommendation"];

interface EditorState {
  readonly recommendation: PatientRecommendation | null;
  readonly visitId: string;
  readonly initialText: string;
  readonly text: string;
}

const recommendationDateFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: "Europe/Kyiv",
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function visitLabel(visit: RecommendationVisit): string {
  const services = visit.services.join(" · ");
  return `${formatPatientVisitDate(visit.occurred_at)} · ${services || visit.public_number}`;
}

function RecommendationsLoading() {
  return (
    <div aria-label="Завантаження рекомендацій" className="patient-recommendations-loading" role="status">
      <span />
      <span />
      <span />
    </div>
  );
}

function mergeRecommendation(
  current: PatientRecommendation,
  latest: VisitRecommendation,
): PatientRecommendation {
  return {
    ...current,
    author: { id: latest.author_id, display_name: latest.author_name },
    text: latest.text,
    version: latest.version,
    created_at: latest.created_at,
    updated_at: latest.updated_at,
  };
}

export function PatientRecommendationsTab({ patientId }: { readonly patientId: string }) {
  const [recommendations, setRecommendations] = useState<readonly PatientRecommendation[]>([]);
  const [eligibleVisits, setEligibleVisits] = useState<readonly RecommendationVisit[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [confirmClose, setConfirmClose] = useState(false);
  const [needsVersionRefresh, setNeedsVersionRefresh] = useState(false);
  const editorDialogRef = useRef<HTMLElement>(null);
  const editorTextRef = useRef<HTMLTextAreaElement>(null);
  const editorTriggerRef = useRef<HTMLButtonElement | null>(null);
  const historyGuardReleaseRef = useRef<(() => void) | null>(null);
  const requestCloseRef = useRef<() => void>(() => undefined);

  const load = useCallback(async (
    cursor: string | null = null,
    background = false,
  ): Promise<RecommendationResponse | null> => {
    if (!background) {
      if (cursor === null) setIsLoading(true);
      else setIsLoadingMore(true);
    }
    setError(null);
    const result = await apiClient.GET("/api/v1/patients/{patient_id}/recommendations", {
      params: {
        path: { patient_id: patientId },
        ...(cursor === null ? {} : { query: { cursor } }),
      },
    }).catch(() => null);
    if (!background) {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
    if (result === null) {
      setError("Немає зв’язку із сервером. Рекомендації не завантажено.");
      return null;
    }
    if (result.data === undefined) {
      setError(result.error.message);
      return null;
    }
    setRecommendations((current) => cursor === null
      ? result.data.recommendations
      : [...current, ...result.data.recommendations]);
    setEligibleVisits(result.data.eligible_visits);
    setNextCursor(result.data.next_cursor);
    return result.data;
  }, [patientId]);

  useEffect(() => {
    void load();
  }, [load]);

  const dirty = editor !== null && editor.text !== editor.initialText;
  useEffect(() => {
    if (!dirty) return undefined;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    const guardAppNavigation = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target : null;
      if (
        target === null
        || editorDialogRef.current?.contains(target) === true
        || target.closest("a[href], button") === null
      ) return;
      event.preventDefault();
      event.stopPropagation();
      setConfirmClose(true);
      window.setTimeout(() => { editorTextRef.current?.focus(); }, 0);
    };
    window.addEventListener("beforeunload", warn);
    document.addEventListener("click", guardAppNavigation, true);
    return () => {
      window.removeEventListener("beforeunload", warn);
      document.removeEventListener("click", guardAppNavigation, true);
    };
  }, [dirty]);

  const selectedVisit = useMemo(
    () => editor === null ? null : (eligibleVisits.find((visit) => visit.id === editor.visitId) ?? editor.recommendation?.visit ?? null),
    [editor, eligibleVisits],
  );

  const closeEditor = useCallback(() => {
    const trigger = editorTriggerRef.current;
    historyGuardReleaseRef.current?.();
    historyGuardReleaseRef.current = null;
    setEditor(null);
    setEditorError(null);
    setConfirmClose(false);
    setNeedsVersionRefresh(false);
    window.setTimeout(() => { trigger?.focus(); }, 0);
  }, []);

  const openCreate = () => {
    const visit = eligibleVisits[0];
    if (visit === undefined) return;
    setEditor({ recommendation: null, visitId: visit.id, initialText: "", text: "" });
    setEditorError(null);
    setConfirmClose(false);
    setNeedsVersionRefresh(false);
    setSuccess(null);
  };

  const openEdit = (recommendation: PatientRecommendation) => {
    setEditor({
      recommendation,
      visitId: recommendation.visit.id,
      initialText: recommendation.text,
      text: recommendation.text,
    });
    setEditorError(null);
    setConfirmClose(false);
    setNeedsVersionRefresh(false);
    setSuccess(null);
  };

  const requestClose = useCallback(() => {
    if (isSaving) return;
    if (dirty) {
      setConfirmClose(true);
      return;
    }
    closeEditor();
  }, [closeEditor, dirty, isSaving]);

  useEffect(() => {
    requestCloseRef.current = requestClose;
  }, [requestClose]);

  const editorOpen = editor !== null;
  useEffect(() => {
    if (!editorOpen) return undefined;
    const originalState: unknown = window.history.state;
    if (
      typeof originalState !== "object"
      || originalState === null
      || !("idx" in originalState)
      || typeof originalState.idx !== "number"
      || !window.location.pathname.startsWith(`/patients/${patientId}/`)
    ) return undefined;
    const marker = `${patientId}-${Date.now().toString(36)}`;
    const url = window.location.href;
    const guardedState = { ...originalState, podoriaRecommendationGuard: marker };
    let active = true;
    window.history.pushState(guardedState, "", url);
    const onPopState = () => {
      if (!active) return;
      requestCloseRef.current();
      if (historyGuardReleaseRef.current !== null) {
        window.history.pushState(guardedState, "", url);
      }
    };
    window.addEventListener("popstate", onPopState);
    const release = () => {
      if (!active) return;
      active = false;
      window.removeEventListener("popstate", onPopState);
      const state = window.history.state as { podoriaRecommendationGuard?: unknown } | null;
      if (state?.podoriaRecommendationGuard === marker) window.history.back();
    };
    historyGuardReleaseRef.current = release;
    return () => {
      if (active) {
        active = false;
        window.removeEventListener("popstate", onPopState);
        const state = window.history.state as { podoriaRecommendationGuard?: unknown } | null;
        if (state?.podoriaRecommendationGuard === marker) {
          window.history.replaceState(originalState, "", url);
        }
      }
      if (historyGuardReleaseRef.current === release) historyGuardReleaseRef.current = null;
    };
  }, [editorOpen, patientId]);

  useEffect(() => {
    if (!editorOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    editorTextRef.current?.focus();
    return () => { document.body.style.overflow = previousOverflow; };
  }, [editorOpen]);

  useEffect(() => {
    if (!editorOpen) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        requestClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = editorDialogRef.current?.querySelectorAll<HTMLElement>(
        "button:not(:disabled), select:not(:disabled), textarea:not(:disabled), [href], [tabindex]:not([tabindex='-1'])",
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
  }, [editorOpen, requestClose]);

  const refreshExactRecommendation = useCallback(async (
    recommendation: PatientRecommendation,
  ): Promise<boolean> => {
    const result = await apiClient.GET(
      "/api/v1/visits/{visit_id}/recommendations/{recommendation_id}",
      {
        params: {
          path: {
            visit_id: recommendation.visit.id,
            recommendation_id: recommendation.id,
          },
        },
      },
    ).catch(() => null);
    if (result?.data === undefined) return false;
    const latest = mergeRecommendation(recommendation, result.data);
    setRecommendations((current) => current.map((item) => item.id === latest.id ? latest : item));
    setEditor((current) => current === null || current.recommendation?.id !== latest.id
      ? current
      : { ...current, recommendation: latest, initialText: latest.text });
    return true;
  }, []);

  const retryVersionRefresh = async () => {
    if (editor?.recommendation === null || editor?.recommendation === undefined || isSaving) return;
    setIsSaving(true);
    setEditorError(null);
    const refreshed = await refreshExactRecommendation(editor.recommendation);
    setIsSaving(false);
    setNeedsVersionRefresh(!refreshed);
    setEditorError(refreshed
      ? "Актуальну версію завантажено, а ваш текст збережено у формі. Перевірте й збережіть ще раз."
      : "Не вдалося оновити версію. Перевірте зв’язок і повторіть спробу.");
  };

  const submit = async (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (editor === null || isSaving || needsVersionRefresh) return;
    const text = editor.text.trim();
    if (text === "") {
      setEditorError("Напишіть рекомендацію перед збереженням.");
      return;
    }
    setIsSaving(true);
    setEditorError(null);
    setConfirmClose(false);
    const result = editor.recommendation === null
      ? await apiClient.POST("/api/v1/visits/{visit_id}/recommendations", {
        params: { path: { visit_id: editor.visitId } },
        headers: csrfHeaders(),
        body: { text },
      }).catch(() => null)
      : await apiClient.PATCH("/api/v1/visits/{visit_id}/recommendations/{recommendation_id}", {
        params: {
          path: {
            visit_id: editor.visitId,
            recommendation_id: editor.recommendation.id,
          },
        },
        headers: csrfHeaders(),
        body: { text, version: editor.recommendation.version },
      }).catch(() => null);
    if (result === null) {
      setIsSaving(false);
      setEditorError("Немає зв’язку із сервером. Текст лишився у формі — повторіть спробу.");
      return;
    }
    if (result.data === undefined) {
      if (result.error.code === "recommendation_version_conflict" && editor.recommendation !== null) {
        setNeedsVersionRefresh(true);
        const refreshed = await refreshExactRecommendation(editor.recommendation);
        setIsSaving(false);
        setNeedsVersionRefresh(!refreshed);
        setEditorError(refreshed
          ? "Рекомендацію вже оновили. Актуальну версію завантажено, а ваш текст збережено у формі. Перевірте й збережіть ще раз."
          : "Рекомендацію вже оновили, але актуальну версію завантажити не вдалося. Перевірте зв’язок і оновіть версію.");
        return;
      }
      setIsSaving(false);
      setEditorError(result.error.message);
      return;
    }
    const edited = editor.recommendation !== null;
    if (editor.recommendation !== null) {
      const updated = mergeRecommendation(editor.recommendation, result.data);
      setRecommendations((current) => current.map((item) => item.id === updated.id ? updated : item));
    } else {
      const visit = eligibleVisits.find((item) => item.id === editor.visitId);
      if (visit !== undefined) {
        const created: PatientRecommendation = {
          id: result.data.id,
          visit,
          author: { id: result.data.author_id, display_name: result.data.author_name },
          text: result.data.text,
          version: result.data.version,
          created_at: result.data.created_at,
          updated_at: result.data.updated_at,
          can_edit: true,
        };
        setRecommendations((current) => [created, ...current]);
      }
    }
    setIsSaving(false);
    closeEditor();
    setSuccess(edited ? "Рекомендацію оновлено й зафіксовано в журналі дій." : "Рекомендацію додано до завершеного візиту.");
    await load(null, true);
  };

  return (
    <section className="surface patient-archive patient-recommendations" aria-labelledby="patient-recommendations-title">
      <header className="patient-archive__header">
        <div>
          <p className="eyebrow">Після завершених прийомів</p>
          <h2 id="patient-recommendations-title">Рекомендації</h2>
          <p>Кожен запис зберігає дату, автора та прив’язку до конкретного завершеного візиту.</p>
        </div>
        <button className="button button--primary" disabled={isLoading || eligibleVisits.length === 0} onClick={(event) => { editorTriggerRef.current = event.currentTarget; openCreate(); }} type="button"><Icon name="plus" />Додати рекомендацію</button>
      </header>

      {success === null ? null : <div className="success-banner" role="status"><Icon name="check" /><span>{success}</span></div>}
      {isLoading ? <RecommendationsLoading /> : null}
      {!isLoading && error !== null && recommendations.length === 0 ? (
        <div className="patient-archive-state" role="alert"><Icon name="warning" /><div><strong>Не вдалося завантажити рекомендації</strong><p>{error}</p></div><button className="button button--secondary" onClick={() => { void load(); }} type="button"><Icon name="refresh" />Повторити</button></div>
      ) : null}
      {!isLoading && error === null && recommendations.length === 0 ? (
        <div className="patient-archive-state patient-archive-state--empty"><Icon name="tasks" /><div><strong>Рекомендацій ще немає</strong><p>{eligibleVisits.length === 0 ? "Вони стануть доступними після завершення першого візиту." : "Додайте план домашнього догляду або наступні кроки після прийому."}</p></div></div>
      ) : null}

      {recommendations.length > 0 ? (
        <div className="patient-recommendation-list">
          {recommendations.map((recommendation) => (
            <article className="patient-recommendation-card" key={recommendation.id}>
              <header>
                <div><span className="avatar avatar--lilac">{recommendation.author.display_name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("")}</span><span><strong>{recommendation.author.display_name}</strong><small>{recommendation.visit.public_number} · {visitLabel(recommendation.visit)}</small></span></div>
                <time dateTime={recommendation.updated_at}>{recommendationDateFormatter.format(new Date(recommendation.updated_at))}</time>
              </header>
              <p>{recommendation.text}</p>
              <footer>
                <span><Icon name="lock" />Медична рекомендація · версія {recommendation.version}</span>
                {recommendation.can_edit ? <button className="text-action" onClick={(event) => { editorTriggerRef.current = event.currentTarget; openEdit(recommendation); }} type="button">Редагувати</button> : null}
              </footer>
            </article>
          ))}
        </div>
      ) : null}
      {error !== null && recommendations.length > 0 ? <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div> : null}
      {nextCursor === null ? null : <div className="patient-archive__more"><button className="button button--secondary" disabled={isLoadingMore} onClick={() => { void load(nextCursor); }} type="button">{isLoadingMore ? "Завантажуємо…" : "Показати попередні рекомендації"}</button></div>}

      {editor === null ? null : (
        <div className="modal-layer patient-recommendation-editor" onMouseDown={(event) => { if (event.currentTarget === event.target) requestClose(); }} role="presentation">
          <section aria-labelledby="recommendation-editor-title" aria-modal="true" className="modal-card" ref={editorDialogRef} role="dialog">
            <header className="modal-card__header">
              <div><p className="eyebrow">Завершений візит</p><h2 id="recommendation-editor-title">{editor.recommendation === null ? "Нова рекомендація" : "Редагувати рекомендацію"}</h2><p>{selectedVisit === null ? "Оберіть візит" : visitLabel(selectedVisit)}</p></div>
              <button aria-label="Закрити рекомендацію" className="icon-button" disabled={isSaving} onClick={requestClose} type="button"><Icon name="close" /></button>
            </header>
            <form onSubmit={(event) => { void submit(event); }}>
              <div className="modal-card__body patient-recommendation-form">
                {editor.recommendation === null ? (
                  <label className="form-field"><span>Завершений візит</span><select disabled={isSaving} onChange={(event) => { setEditor((current) => current === null ? null : { ...current, visitId: event.target.value }); setEditorError(null); }} value={editor.visitId}>{eligibleVisits.map((visit) => <option key={visit.id} value={visit.id}>{visitLabel(visit)}</option>)}</select></label>
                ) : <div className="patient-recommendation-visit"><Icon name="calendar" /><span><strong>{editor.recommendation.visit.public_number}</strong><small>{visitLabel(editor.recommendation.visit)}</small></span></div>}
                <label className="form-field"><span>Рекомендація</span><textarea aria-describedby="recommendation-text-help" aria-label="Рекомендація" disabled={isSaving} maxLength={10000} onChange={(event) => { setEditor((current) => current === null ? null : { ...current, text: event.target.value }); setEditorError(null); setConfirmClose(false); }} placeholder="Домашній догляд, обмеження, контроль або наступні кроки…" ref={editorTextRef} required rows={8} value={editor.text} /><small id="recommendation-text-help">{editor.text.length.toLocaleString("uk-UA")} / 10 000 символів</small></label>
                {editorError === null ? null : <div className="form-error patient-recommendation-form__error" role="alert"><span><Icon name="warning" />{editorError}</span>{needsVersionRefresh ? <button className="button button--secondary" disabled={isSaving} onClick={() => { void retryVersionRefresh(); }} type="button">{isSaving ? "Оновлюємо…" : "Оновити актуальну версію"}</button> : null}</div>}
                {confirmClose ? <div className="patient-close-warning" role="alert"><span><strong>Є незбережений текст</strong><small>Відкинути зміни й закрити форму?</small></span><div><button className="button button--secondary" disabled={isSaving} onClick={() => { setConfirmClose(false); editorTextRef.current?.focus(); }} type="button">Продовжити</button><button className="button button--danger" disabled={isSaving} onClick={closeEditor} type="button">Відкинути</button></div></div> : null}
              </div>
              <footer className="modal-card__footer"><button className="button button--secondary" disabled={isSaving} onClick={requestClose} type="button">Скасувати</button><button className="button button--primary" disabled={isSaving || needsVersionRefresh || editor.text.trim() === ""} type="submit">{isSaving ? "Зберігаємо…" : "Зберегти рекомендацію"}</button></footer>
            </form>
          </section>
        </div>
      )}
    </section>
  );
}
