import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router";

import { apiClient } from "../api/client";
import type { components, operations } from "../api/schema";
import { Icon } from "../app/Icon";
import { useAuth, csrfHeaders } from "../auth/AuthContext";
import {
  linesAreValid,
  VisitLinesStep,
  type VisitMaterialLine,
  type VisitServiceLine,
} from "./VisitLinesStep";
import { VisitFinishStep, type FinishResult } from "./VisitFinishStep";
import { VisitPhotosStep, type VisitPhoto } from "./VisitPhotosStep";

type Visit = components["schemas"]["VisitResponse"];
type DetectedCondition = components["schemas"]["DetectedConditionEnum"];
type VisitDraftUpdate = NonNullable<operations["visit_draft_update"]["requestBody"]>["content"]["application/json"];
type FieldErrors = Readonly<Record<string, readonly string[]>>;
type SaveState = "idle" | "pending" | "saving" | "saved" | "error";

const CONDITIONS = [
  { value: "HYPERKERATOSIS", label: "Гіперкератоз" },
  { value: "FISSURES", label: "Тріщини" },
  { value: "NAIL_DEFORMATION", label: "Деформація нігтя" },
  { value: "REDNESS", label: "Почервоніння" },
  { value: "EDEMA", label: "Набряк" },
  { value: "TENDERNESS", label: "Болісність" },
] as const satisfies readonly { readonly value: DetectedCondition; readonly label: string }[];

const dateTimeFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: "Europe/Kyiv",
  weekday: "short",
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const moneyFormatter = new Intl.NumberFormat("uk-UA", {
  style: "currency",
  currency: "UAH",
  minimumFractionDigits: 2,
});

function fieldMessage(errors: FieldErrors, field: string): string | null {
  return errors[field]?.[0] ?? null;
}

function examinationFingerprint(value: {
  readonly complaints: string;
  readonly hasNoComplaints: boolean;
  readonly objectiveExamination: string;
  readonly detectedConditions: readonly DetectedCondition[];
  readonly podologistNotes: string;
}): string {
  return JSON.stringify(value);
}

function linesFingerprint(value: {
  readonly serviceLines: readonly VisitServiceLine[];
  readonly materialLines: readonly VisitMaterialLine[];
}): string {
  return JSON.stringify({
    serviceLines: value.serviceLines.map((line) => ({
      service_id: line.service_id,
      quantity: line.quantity,
    })),
    materialLines: value.materialLines.map((line) => ({
      lot_id: line.lot_id,
      quantity: line.quantity,
    })),
  });
}

function VisitLoading() {
  return (
    <section className="visit-state panel" role="status">
      <span className="spinner" aria-hidden="true" />
      <div><h1>Відкриваємо прийом</h1><p>Завантажуємо актуальну чернетку огляду…</p></div>
    </section>
  );
}

export function VisitPage() {
  const { state } = useAuth();
  const { visitId } = useParams<{ visitId: string }>();
  const navigate = useNavigate();
  const [visit, setVisit] = useState<Visit | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [complaints, setComplaints] = useState("");
  const [hasNoComplaints, setHasNoComplaints] = useState(false);
  const [objectiveExamination, setObjectiveExamination] = useState("");
  const [detectedConditions, setDetectedConditions] = useState<readonly DetectedCondition[]>([]);
  const [podologistNotes, setPodologistNotes] = useState("");
  const [serviceLines, setServiceLines] = useState<readonly VisitServiceLine[]>([]);
  const [materialLines, setMaterialLines] = useState<readonly VisitMaterialLine[]>([]);
  const [savedExaminationFingerprint, setSavedExaminationFingerprint] = useState("");
  const [savedLinesFingerprint, setSavedLinesFingerprint] = useState("");
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [isSaving, setIsSaving] = useState(false);
  const [showLeaveConfirm, setShowLeaveConfirm] = useState(false);
  const [activeStep, setActiveStep] = useState<1 | 2 | 3 | 4>(1);
  const [finishResult, setFinishResult] = useState<FinishResult | null>(null);

  const hydrate = useCallback((value: Visit) => {
    setVisit(value);
    setComplaints(value.complaints);
    setHasNoComplaints(value.has_no_complaints);
    setObjectiveExamination(value.objective_examination);
    setDetectedConditions(value.detected_conditions);
    setPodologistNotes(value.podologist_notes);
    setServiceLines(value.service_lines);
    setMaterialLines(value.material_lines);
    setSavedExaminationFingerprint(examinationFingerprint({
      complaints: value.complaints,
      hasNoComplaints: value.has_no_complaints,
      objectiveExamination: value.objective_examination,
      detectedConditions: value.detected_conditions,
      podologistNotes: value.podologist_notes,
    }));
    setSavedLinesFingerprint(linesFingerprint({
      serviceLines: value.service_lines,
      materialLines: value.material_lines,
    }));
    if (value.status === "COMPLETED") setActiveStep(4);
  }, []);

  const load = useCallback(async () => {
    if (visitId === undefined) return;
    setIsLoading(true);
    setLoadError(null);
    const result = await apiClient.GET("/api/v1/visits/{visit_id}", {
      params: { path: { visit_id: visitId } },
    }).catch(() => null);
    setIsLoading(false);
    if (result === null) {
      setLoadError("Немає зв’язку із сервером. Перевірте мережу й повторіть спробу.");
      return;
    }
    if (result.data === undefined) {
      setLoadError(result.error.message);
      return;
    }
    hydrate(result.data);
  }, [hydrate, visitId]);

  useEffect(() => {
    void load();
  }, [load]);

  const currentExaminationFingerprint = useMemo(() => examinationFingerprint({
    complaints,
    hasNoComplaints,
    objectiveExamination,
    detectedConditions,
    podologistNotes,
  }), [complaints, detectedConditions, hasNoComplaints, objectiveExamination, podologistNotes]);
  const currentLinesFingerprint = useMemo(() => linesFingerprint({
    serviceLines,
    materialLines,
  }), [materialLines, serviceLines]);
  const examinationDirty = visit !== null
    && currentExaminationFingerprint !== savedExaminationFingerprint;
  const linesDirty = visit !== null && currentLinesFingerprint !== savedLinesFingerprint;
  const dirty = examinationDirty || linesDirty;
  const activeDirty = activeStep === 1 ? examinationDirty : activeStep === 2 ? linesDirty : false;
  const complaintsValid = hasNoComplaints !== Boolean(complaints.trim());
  const currentLinesValid = linesAreValid(serviceLines, materialLines);
  const activeValid = activeStep === 1 ? complaintsValid : activeStep === 2 ? currentLinesValid : true;

  useEffect(() => {
    if (!dirty) return;
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => { window.removeEventListener("beforeunload", beforeUnload); };
  }, [dirty]);

  const saveDraft = useCallback(async (source: "auto" | "manual") => {
    if (visit === null || isSaving || !activeValid || !activeDirty) return;
    setIsSaving(true);
    setSaveState("saving");
    setError(null);
    setFieldErrors({});
    const body: VisitDraftUpdate = activeStep === 1
      ? {
          version: visit.version,
          complaints,
          has_no_complaints: hasNoComplaints,
          objective_examination: objectiveExamination,
          detected_conditions: [...detectedConditions],
          podologist_notes: podologistNotes,
        }
      : {
          version: visit.version,
          service_lines: serviceLines.map((line) => ({
            service_id: line.service_id,
            quantity: line.quantity,
          })),
          material_lines: materialLines.map((line) => ({
            lot_id: line.lot_id,
            quantity: line.quantity,
          })),
        };
    const result = await apiClient.PUT("/api/v1/visits/{visit_id}", {
      params: { path: { visit_id: visit.id } },
      body,
      headers: csrfHeaders(),
    }).catch(() => null);
    setIsSaving(false);
    if (result === null) {
      setSaveState("error");
      setError("Немає зв’язку із сервером. Чернетка залишилася у формі — повторіть збереження.");
      return;
    }
    if (result.data === undefined) {
      setSaveState("error");
      setError(result.error.code === "visit_version_conflict"
        ? "Чернетка змінилася в іншому вікні. Ваші дані збережені у формі; оновіть сторінку після перевірки."
        : result.error.message);
      setFieldErrors(result.error.fields);
      return;
    }
    hydrate(result.data);
    setSaveState("saved");
    if (source === "manual") setError(null);
  }, [activeDirty, activeStep, activeValid, complaints, detectedConditions, hasNoComplaints, hydrate, isSaving, materialLines, objectiveExamination, podologistNotes, serviceLines, visit]);

  useEffect(() => {
    if (!activeDirty || !activeValid || isSaving) return;
    setSaveState("pending");
    const timeout = window.setTimeout(() => { void saveDraft("auto"); }, 1400);
    return () => { window.clearTimeout(timeout); };
  }, [activeDirty, activeValid, currentExaminationFingerprint, currentLinesFingerprint, isSaving, saveDraft]);

  if (state.status !== "authenticated") return null;
  if (state.session.user.role === "reception") return <Navigate replace to="/?notice=forbidden" />;
  if (visitId === undefined) return <Navigate replace to="/calendar" />;
  if (isLoading) return <VisitLoading />;
  if (visit === null) {
    return (
      <section className="visit-state panel" role="alert">
        <span className="visit-state__icon"><Icon name="warning" /></span>
        <div><h1>Не вдалося відкрити прийом</h1><p>{loadError ?? "Прийом не знайдено."}</p></div>
        <button className="button button--secondary" onClick={() => { void load(); }} type="button">Повторити</button>
      </section>
    );
  }

  const toggleCondition = (condition: DetectedCondition, checked: boolean) => {
    setDetectedConditions((current) => checked
      ? [...current, condition]
      : current.filter((value) => value !== condition));
    setError(null);
    setFieldErrors({});
  };
  const requestBack = () => {
    if (dirty) {
      setShowLeaveConfirm(true);
      return;
    }
    void navigate("/calendar");
  };
  const replacePhotos = (photos: readonly VisitPhoto[]) => {
    setVisit((current) => current === null ? current : { ...current, photos: [...photos] });
  };
  const saveLabel = saveState === "saving"
    ? "Зберігаємо…"
    : saveState === "pending"
      ? "Автозбереження очікує"
      : saveState === "saved"
        ? "Чернетку збережено"
        : saveState === "error"
          ? "Не збережено"
          : "Змін немає";

  return (
    <>
      <header className="page-heading visit-heading">
        <div>
          <p className="eyebrow">Прийом · TP-604</p>
          <h1>{visit.patient.display_name}</h1>
          <p>{visit.public_number} · {visit.patient.public_number} · {visit.appointment.service_name}</p>
        </div>
        <div className="visit-heading__actions">
          <button className="button button--secondary" onClick={requestBack} type="button"><Icon name="arrow-left" />До календаря</button>
          <span className="visit-status"><span aria-hidden="true" />{visit.appointment.status_label}</span>
        </div>
      </header>

      <section className="visit-summary panel" aria-label="Дані прийому">
        <div><span>Запис</span><strong>{visit.appointment.public_number}</strong></div>
        <div><span>Дата й час</span><strong>{dateTimeFormatter.format(new Date(visit.appointment.starts_at))}</strong></div>
        <div><span>Спеціаліст</span><strong>{visit.specialist.display_name}</strong></div>
        <div><span>Кабінет</span><strong>{visit.appointment.room_name}</strong></div>
      </section>

      <nav className="visit-steps panel" aria-label="Кроки оформлення прийому">
        <ol>
          <li aria-current={activeStep === 1 ? "step" : undefined} className={`visit-step${activeStep === 1 ? " visit-step--active" : ""}`}>
            <button disabled={activeStep !== 1 && (activeDirty || !activeValid || isSaving)} onClick={() => { setActiveStep(1); setError(null); setFieldErrors({}); }} type="button"><span>1</span><strong>Скарги та огляд</strong><small>{activeStep === 1 ? "Поточний крок" : "Збережено"}</small></button>
          </li>
          <li aria-current={activeStep === 2 ? "step" : undefined} className={`visit-step${activeStep === 2 ? " visit-step--active" : ""}`}>
            <button disabled={activeStep !== 2 && (activeDirty || !activeValid || isSaving)} onClick={() => { setActiveStep(2); setError(null); setFieldErrors({}); }} type="button"><span>2</span><strong>Послуги й матеріали</strong><small>{activeStep === 2 ? "Поточний крок" : "Доступно"}</small></button>
          </li>
          <li aria-current={activeStep === 3 ? "step" : undefined} className={`visit-step${activeStep === 3 ? " visit-step--active" : ""}`}>
            <button disabled={activeStep !== 3 && (activeDirty || !activeValid || isSaving)} onClick={() => { setActiveStep(3); setError(null); setFieldErrors({}); }} type="button"><span>3</span><strong>Фото до / після</strong><small>{activeStep === 3 ? "Поточний крок" : "Доступно"}</small></button>
          </li>
          <li aria-current={activeStep === 4 ? "step" : undefined} className={`visit-step${activeStep === 4 ? " visit-step--active" : ""}`}>
            <button disabled={activeStep !== 4 && (activeDirty || !activeValid || isSaving)} onClick={() => { setActiveStep(4); setError(null); setFieldErrors({}); }} type="button"><span>4</span><strong>Завершення</strong><small>{visit.status === "COMPLETED" ? "Завершено" : activeStep === 4 ? "Поточний крок" : "Доступно"}</small></button>
          </li>
        </ol>
      </nav>

      <div className="visit-workspace">
        {activeStep === 1 ? <section className="visit-examination panel" aria-labelledby="visit-examination-title">
          <header>
            <div><p className="eyebrow">Крок 1 із 4</p><h2 id="visit-examination-title">Скарги та об’єктивний огляд</h2><p>Чернетка не списує матеріали, не створює оплату та не завершує прийом.</p></div>
            <span aria-live="polite" className={`visit-save-state visit-save-state--${saveState}`} role="status"><span aria-hidden="true" />{saveLabel}</span>
          </header>

          {error ? <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div> : null}
          {!complaintsValid ? <div className="form-message form-message--warning" role="alert"><Icon name="warning" /><span>Укажіть скарги або виберіть «Скарг немає», щоб зберегти чернетку.</span></div> : null}

          <div className="visit-form-grid">
            <label className="form-field visit-form-wide">
              <span>Скарги / причина звернення</span>
              <textarea aria-describedby="visit-complaints-hint" aria-label="Скарги / причина звернення" disabled={hasNoComplaints || isSaving || !visit.editable} maxLength={4000} onChange={(event) => { setComplaints(event.target.value); setError(null); setFieldErrors({}); }} placeholder="Опишіть скарги або причину звернення" rows={4} value={complaints} />
              <small id="visit-complaints-hint">Підставлено із запису; можна уточнити під час прийому.</small>
              {fieldMessage(fieldErrors, "complaints") ? <small className="field-error">{fieldMessage(fieldErrors, "complaints")}</small> : null}
            </label>
            <label className="settings-check visit-form-wide">
              <input aria-label="Скарг немає" checked={hasNoComplaints} disabled={isSaving || !visit.editable} onChange={(event) => { setHasNoComplaints(event.target.checked); if (event.target.checked) setComplaints(""); setError(null); setFieldErrors({}); }} type="checkbox" />
              <span><strong>Скарг немає</strong><small>Явне підтвердження для профілактичного прийому.</small></span>
            </label>
            <label className="form-field visit-form-wide">
              <span>Об’єктивний огляд</span>
              <textarea aria-label="Об’єктивний огляд" disabled={isSaving || !visit.editable} maxLength={10000} onChange={(event) => { setObjectiveExamination(event.target.value); setError(null); }} placeholder="Опишіть стан шкіри, нігтів та інші об’єктивні ознаки" rows={6} value={objectiveExamination} />
            </label>
            <fieldset className="visit-condition-fieldset visit-form-wide" disabled={isSaving || !visit.editable}>
              <legend>Виявлені стани</legend>
              <p>Можна вибрати кілька станів.</p>
              <div>{CONDITIONS.map((condition) => (
                <label key={condition.value}><input checked={detectedConditions.includes(condition.value)} onChange={(event) => { toggleCondition(condition.value, event.target.checked); }} type="checkbox" /><span>{condition.label}</span></label>
              ))}</div>
              {fieldMessage(fieldErrors, "detected_conditions") ? <small className="field-error">{fieldMessage(fieldErrors, "detected_conditions")}</small> : null}
            </fieldset>
            <label className="form-field visit-form-wide">
              <span>Нотатки подолога · необов’язково</span>
              <textarea aria-label="Нотатки подолога · необов’язково" disabled={isSaving || !visit.editable} maxLength={10000} onChange={(event) => { setPodologistNotes(event.target.value); setError(null); }} placeholder="Робочі клінічні нотатки" rows={4} value={podologistNotes} />
              <small>Це медичні дані: ресепшн не має до них доступу.</small>
            </label>
          </div>

          <footer className="visit-workspace__footer">
            <div><strong>Версія чернетки: {visit.version}</strong><small>Автозбереження спрацьовує після паузи; доступне й ручне збереження.</small></div>
            <div>
              <button className="button button--secondary" disabled={!examinationDirty || isSaving || !complaintsValid || !visit.editable} onClick={() => { void saveDraft("manual"); }} type="button">{isSaving ? "Зберігаємо…" : "Зберегти чернетку"}</button>
              <button aria-describedby="visit-next-hint" className="button button--primary" disabled={examinationDirty || isSaving || !complaintsValid || !visit.editable} onClick={() => { setActiveStep(2); setSaveState("idle"); }} type="button">Далі: послуги й матеріали</button>
            </div>
          </footer>
          <p className="visit-next-hint" id="visit-next-hint">{examinationDirty ? "Збережіть зміни огляду перед переходом." : "Крок 2 доступний: додайте послуги та фактично використані матеріали."}</p>
        </section> : activeStep === 2 ? (
          <section className="visit-examination visit-lines-panel panel" aria-labelledby="visit-lines-title">
            <header>
              <div><p className="eyebrow">Крок 2 із 4</p><h2 id="visit-lines-title">Послуги й матеріали</h2><p>Послуги формують майбутню суму, матеріали лише резервуються у чернетці без списання.</p></div>
              <span aria-live="polite" className={`visit-save-state visit-save-state--${saveState}`} role="status"><span aria-hidden="true" />{saveLabel}</span>
            </header>

            {error ? <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div> : null}
            {!currentLinesValid ? <div className="form-message form-message--warning" role="alert"><Icon name="warning" /><span>Перевірте кількість послуг і матеріалів: значення мають бути додатними та не перевищувати доступний залишок.</span></div> : null}

            <VisitLinesStep
              disabled={isSaving || !visit.editable}
              fieldError={fieldMessage(fieldErrors, "material_lines") ?? fieldMessage(fieldErrors, "service_lines")}
              materialLines={materialLines}
              onMaterialLinesChange={(lines) => { setMaterialLines(lines); setError(null); setFieldErrors({}); }}
              onServiceLinesChange={(lines) => { setServiceLines(lines); setError(null); setFieldErrors({}); }}
              serviceLines={serviceLines}
              visitId={visit.id}
            />

            <footer className="visit-workspace__footer">
              <div><strong>Версія чернетки: {visit.version}</strong><small>Finish повторно перевірить актуальний залишок і лише тоді створить складські рухи.</small></div>
              <div>
                <button className="button button--secondary" disabled={linesDirty || isSaving} onClick={() => { setActiveStep(1); setSaveState("idle"); }} type="button">Назад до огляду</button>
                <button className="button button--secondary" disabled={!linesDirty || isSaving || !currentLinesValid || !visit.editable} onClick={() => { void saveDraft("manual"); }} type="button">{isSaving ? "Зберігаємо…" : "Зберегти чернетку"}</button>
                <button aria-describedby="visit-next-hint" className="button button--primary" disabled={linesDirty || isSaving || !currentLinesValid || !visit.editable} onClick={() => { setActiveStep(3); setSaveState("idle"); }} type="button">Далі: фото</button>
              </div>
            </footer>
            <p className="visit-next-hint" id="visit-next-hint">{linesDirty ? "Збережіть послуги й матеріали перед переходом." : "Крок 3 доступний: додайте приватні фото до або після процедури."}</p>
          </section>
        ) : activeStep === 3 ? (
          <section className="visit-examination visit-photos-panel panel" aria-labelledby="visit-photos-title">
            <header>
              <div><p className="eyebrow">Крок 3 із 4</p><h2 id="visit-photos-title">Фото до та після процедури</h2><p>Кожне фото однозначно належить цьому прийому й окремому блоку BEFORE або AFTER.</p></div>
              <span className="visit-save-state visit-save-state--saved" role="status"><span aria-hidden="true" />Зберігається одразу</span>
            </header>

            <VisitPhotosStep
              editable={visit.editable}
              onPhotosChange={replacePhotos}
              photos={visit.photos}
              visitId={visit.id}
            />

            <footer className="visit-workspace__footer">
              <div><strong>{visit.photos.length} фото у прийомі</strong><small>Чернетку можна продовжити пізніше; фото не впливають на склад або фінанси.</small></div>
              <div>
                <button className="button button--secondary" onClick={() => { setActiveStep(2); }} type="button">Назад до послуг</button>
                <button className="button button--primary" disabled={!visit.editable} onClick={() => { setActiveStep(4); }} type="button">Далі: завершення</button>
              </div>
            </footer>
            <p className="visit-next-hint">На кроці 4 перевірте суму, рекомендації, передачу на оплату та за потреби створіть наступний запис.</p>
          </section>
        ) : visit.status === "COMPLETED" ? (
          <section className="visit-completed panel" role="status">
            <span className="visit-completed__icon"><Icon name="check" /></span>
            <div>
              <p className="eyebrow">Прийом завершено</p>
              <h2>{visit.payment_handoff_requested ? "Передано ресепшну на оплату" : "Збережено як завершений"}</h2>
              <p>Сума до оплати: <strong>{moneyFormatter.format((visit.total_minor ?? visit.services_total_minor) / 100)}</strong>. Складські рухи, рекомендації та історія прийому зафіксовані атомарно.</p>
              <dl>
                <div><dt>Фінансове зобов’язання</dt><dd>{finishResult?.receivable.status === "OPEN" || finishResult === null ? "Очікує повної оплати" : finishResult.receivable.status}</dd></div>
                <div><dt>Списано партій</dt><dd>{finishResult?.movement_ids.length ?? visit.material_lines.length}</dd></div>
                <div><dt>Наступний запис</dt><dd>{finishResult?.follow_up_appointment_id ? "Створено" : "Не створювався або дані вже оновлено"}</dd></div>
              </dl>
              <div className="visit-completed__actions">
                <button className="button button--primary" onClick={() => { void navigate("/calendar"); }} type="button">Повернутися до календаря</button>
                <button className="button button--secondary" onClick={() => { void navigate(`/patients/${visit.patient.id}/visits`); }} type="button">Відкрити історію пацієнта</button>
              </div>
              <small>Оплату ще не проведено: це окрема касова дія наступного пакета.</small>
            </div>
          </section>
        ) : (
          <VisitFinishStep
            onBack={() => { setActiveStep(3); }}
            onCompleted={(result) => { setFinishResult(result); hydrate(result.visit); }}
            visit={visit}
          />
        )}
      </div>

      {showLeaveConfirm ? (
        <div className="modal-layer" role="presentation">
          <section aria-labelledby="visit-leave-title" aria-modal="true" className="modal-card visit-leave-dialog" role="dialog">
            <header className="modal-card__header"><div><p className="eyebrow">Незбережена чернетка</p><h2 id="visit-leave-title">Вийти без останніх змін?</h2><p>Незбережені поля прийому буде втрачено.</p></div></header>
            <div className="modal-actions"><button className="button button--secondary" autoFocus onClick={() => { setShowLeaveConfirm(false); }} type="button">Залишитися</button><button className="button button--danger-ghost" onClick={() => { void navigate("/calendar"); }} type="button">Вийти без збереження</button></div>
          </section>
        </div>
      ) : null}
    </>
  );
}
