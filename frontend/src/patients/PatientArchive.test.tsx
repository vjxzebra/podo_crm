import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  jsonResponse,
  medicalPatientDetailFixture,
  patientHistoryVisitFixture,
  patientPhotoArchiveResponseFixture,
  patientRecommendationFixture,
  patientRecommendationResponseFixture,
  patientFixture,
  visitPhotoBeforeFixture,
} from "../test/setup";
import { PatientPhotoArchiveTab } from "./PatientPhotoArchiveTab";
import { PatientRecommendationsTab } from "./PatientRecommendationsTab";
import { PatientDetailPage } from "./PatientDetailPage";
import { PatientVisitHistoryTab } from "./PatientVisitHistoryTab";

afterEach(() => {
  document.cookie = "podoria_csrftoken=; max-age=0; path=/";
});

describe("TP-605 patient visit archive", () => {
  it("clears a prior medical projection and ignores a late response when the patient route changes", async () => {
    const delayedPatientId = "7f4b1c07-bf6a-46ca-9d4e-838d6eb27211";
    const inaccessiblePatientId = "49143a33-4ba6-4d90-af7f-3d1f18621e7b";
    let resolveDelayed: ((response: Response) => void) | undefined;
    const delayedResponse = new Promise<Response>((resolve) => { resolveDelayed = resolve; });
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const path = new URL(input instanceof Request ? input.url : input.toString()).pathname;
      if (path.includes(delayedPatientId)) return delayedResponse;
      if (path.includes(inaccessiblePatientId)) {
        return Promise.resolve(jsonResponse({
          code: "not_found",
          message: "Ресурс не знайдено.",
          fields: {},
          correlation_id: "test-request",
        }, 404));
      }
      return Promise.resolve(jsonResponse(medicalPatientDetailFixture));
    });
    render(
      <MemoryRouter initialEntries={[`/patients/${patientFixture.id}/overview`]}>
        <Link to={`/patients/${delayedPatientId}/overview`}>Відкрити іншу картку</Link>
        <Link to={`/patients/${inaccessiblePatientId}/overview`}>Відкрити недоступну картку</Link>
        <Routes><Route element={<PatientDetailPage />} path="/patients/:patientId/:tab?" /></Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("Латекс")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: "Відкрити іншу картку" }));
    expect(screen.queryByText("Латекс")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(vi.mocked(fetch).mock.calls.some(([input]) => (input instanceof Request ? input.url : input.toString()).includes(delayedPatientId))).toBe(true);
    });
    fireEvent.click(screen.getByRole("link", { name: "Відкрити недоступну картку" }));
    expect(await screen.findByRole("heading", { name: "Картку пацієнта не знайдено" })).toBeInTheDocument();

    await act(async () => {
      resolveDelayed?.(jsonResponse({
        ...medicalPatientDetailFixture,
        id: delayedPatientId,
        first_name: "Чутливі",
        last_name: "Дані",
        display_name: "Чутливі Дані",
      }));
      await Promise.resolve();
    });
    expect(screen.queryByRole("heading", { name: "Чутливі Дані" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Картку пацієнта не знайдено" })).toBeInTheDocument();
  });

  it("renders medical history facts while tolerating the reception-safe projection", async () => {
    const { unmount } = render(<PatientVisitHistoryTab patientId={patientFixture.id} />);

    expect(await screen.findByText("Шкіра спокійна, загоєння без ускладнень.")).toBeInTheDocument();
    expect(screen.getByText("До 1 · Після 1")).toBeInTheDocument();
    expect(screen.getByText("Рекомендацій: 1")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Деталі візиту"));
    expect(screen.getAllByText("Олена Подолог").length).toBeGreaterThan(0);

    unmount();
    const safeVisit = {
      id: patientHistoryVisitFixture.id,
      public_number: patientHistoryVisitFixture.public_number,
      occurred_at: patientHistoryVisitFixture.occurred_at,
      completed_at: patientHistoryVisitFixture.completed_at,
      status: patientHistoryVisitFixture.status,
      status_label: patientHistoryVisitFixture.status_label,
      services: patientHistoryVisitFixture.services,
      specialist: patientHistoryVisitFixture.specialist,
      total_minor: patientHistoryVisitFixture.total_minor,
    } as const;
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ visits: [safeVisit], next_cursor: null }));
    render(<PatientVisitHistoryTab patientId={patientFixture.id} />);

    await screen.findByText(patientHistoryVisitFixture.public_number, { exact: false });
    expect(screen.queryByLabelText("Медичні матеріали візиту")).not.toBeInTheDocument();
    expect(screen.queryByText("Шкіра спокійна, загоєння без ускладнень.")).not.toBeInTheDocument();
  });

  it("opens private photos in a keyboard carousel with kind tabs, thumbnails and focus return", async () => {
    const secondBefore = {
      ...visitPhotoBeforeFixture,
      id: "d25de2ef-337a-4f8e-9149-c74480586cc1",
      original_name: "before-second.jpg",
      created_at: "2026-07-21T08:13:00Z",
      image_url: "/api/v1/visit-photo-content?token=before-second-original",
      preview_url: "/api/v1/visit-photo-content?token=before-second-preview",
    } as const;
    const archive = {
      ...patientPhotoArchiveResponseFixture,
      visits: [{
        ...patientPhotoArchiveResponseFixture.visits[0],
        photos: [visitPhotoBeforeFixture, secondBefore, patientPhotoArchiveResponseFixture.visits[0].photos[1]],
      }],
    } as const;
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      if (/\/api\/v1\/visits\/[0-9a-f-]+\/photos\/[0-9a-f-]+$/.test(new URL(request.url).pathname)) {
        return Promise.resolve(jsonResponse({
          ...archive.visits[0].photos[2],
          image_url: "/api/v1/visit-photo-content?token=after-refreshed-original",
        }));
      }
      return Promise.resolve(jsonResponse(archive));
    });
    render(<PatientPhotoArchiveTab patientId={patientFixture.id} />);

    const trigger = await screen.findByRole("button", { name: "Відкрити «До процедури», фото 1 у слайдері" });
    fireEvent.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Первинна консультація" });
    expect(within(dialog).getByRole("tab", { name: "До процедури, 2 фото" })).toHaveAttribute("aria-selected", "true");
    expect(within(dialog).getByRole("img", { name: "До процедури: before-procedure.jpg" })).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "ArrowRight" });
    expect(within(dialog).getByRole("img", { name: "До процедури: before-second.jpg" })).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("tab", { name: "Після процедури, 1 фото" }));
    expect(within(dialog).getByRole("img", { name: "Після процедури: after-procedure.webp" })).toBeInTheDocument();

    fireEvent.error(within(dialog).getByRole("img", { name: "Після процедури: after-procedure.webp" }));
    expect(within(dialog).getByRole("alert")).toHaveTextContent("Захищене посилання могло завершити дію");
    fireEvent.click(within(dialog).getByRole("button", { name: "Оновити посилання" }));
    await waitFor(() => { expect(within(dialog).queryByRole("alert")).not.toBeInTheDocument(); });
    await waitFor(() => { expect(within(dialog).getByRole("button", { name: "Закрити перегляд фото" })).toHaveFocus(); });

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Первинна консультація" })).not.toBeInTheDocument();
    await waitFor(() => { expect(trigger).toHaveFocus(); });
  });
});

describe("TP-605 authored recommendations", () => {
  it("keeps every dismissal path locked until a recommendation write finishes", async () => {
    let resolveWrite: ((response: Response) => void) | undefined;
    const pendingWrite = new Promise<Response>((resolve) => { resolveWrite = resolve; });
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      if (request.method === "POST") return pendingWrite;
      return Promise.resolve(jsonResponse(patientRecommendationResponseFixture));
    });
    render(<PatientRecommendationsTab patientId={patientFixture.id} />);
    await screen.findByText(patientRecommendationFixture.text);
    fireEvent.click(screen.getByRole("button", { name: "Додати рекомендацію" }));
    const dialog = screen.getByRole("dialog", { name: "Нова рекомендація" });
    const textarea = within(dialog).getByLabelText("Рекомендація");
    fireEvent.change(textarea, { target: { value: "Запис, який ще зберігається." } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Зберегти рекомендацію" }));

    expect(await within(dialog).findByRole("button", { name: "Зберігаємо…" })).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: "Закрити рекомендацію" })).toBeDisabled();
    expect(textarea).toBeDisabled();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("dialog", { name: "Нова рекомендація" })).toBeInTheDocument();

    await act(async () => {
      resolveWrite?.(jsonResponse({
        id: "19f31b29-8b85-4385-b086-b5896db13fd5",
        author_id: 1,
        author_name: "Тест Адміністратор",
        text: "Запис, який ще зберігається.",
        version: 1,
        created_at: "2026-07-21T12:00:00Z",
        updated_at: "2026-07-21T12:00:00Z",
      }, 201));
      await Promise.resolve();
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Рекомендацію додано");
  });

  it("guards unsaved text and creates a recommendation for a completed visit", async () => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      if (request.method === "POST") {
        return Promise.resolve(jsonResponse({
          id: "a79b32d1-e776-4a0c-b201-792f80a9b5d1",
          author_id: 1,
          author_name: "Тест Адміністратор",
          text: "Новий план домашнього догляду.",
          version: 1,
          created_at: "2026-07-21T10:00:00Z",
          updated_at: "2026-07-21T10:00:00Z",
        }, 201));
      }
      return Promise.resolve(jsonResponse(patientRecommendationResponseFixture));
    });
    render(<PatientRecommendationsTab patientId={patientFixture.id} />);
    await screen.findByText(patientRecommendationFixture.text);
    const addButton = screen.getByRole("button", { name: "Додати рекомендацію" });
    fireEvent.click(addButton);

    const dialog = screen.getByRole("dialog", { name: "Нова рекомендація" });
    expect(document.body.style.overflow).toBe("hidden");
    const textarea = within(dialog).getByLabelText("Рекомендація");
    fireEvent.change(textarea, { target: { value: "Новий план домашнього догляду." } });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(within(dialog).getByRole("alert")).toHaveTextContent("Є незбережений текст");
    fireEvent.click(within(dialog).getByRole("button", { name: "Продовжити" }));
    expect(textarea).toHaveValue("Новий план домашнього догляду.");
    fireEvent.click(within(dialog).getByRole("button", { name: "Зберегти рекомендацію" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Рекомендацію додано");
    await waitFor(() => { expect(addButton).toHaveFocus(); });
    expect(document.body.style.overflow).toBe("");
    const createRequest = fetchMock.mock.calls.find(([input]) => input instanceof Request && input.method === "POST")?.[0];
    expect(createRequest).toBeInstanceOf(Request);
    expect((createRequest as Request).headers.get("X-CSRFToken")).toBe("test-csrf");
    expect(await (createRequest as Request).clone().json()).toEqual({ text: "Новий план домашнього догляду." });
  });

  it("preserves a draft across a version conflict and retries with the refreshed version", async () => {
    let version = 1;
    let patchCount = 0;
    let writeSucceeded = false;
    const patchBodies: unknown[] = [];
    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      if (request.method === "PATCH") {
        patchCount += 1;
        patchBodies.push(await request.clone().json());
        if (patchCount === 1) {
          version = 2;
          return jsonResponse({
            code: "recommendation_version_conflict",
            message: "Рекомендацію вже змінив інший користувач. Оновіть дані.",
            fields: { version: ["Версія рекомендації застаріла."] },
            correlation_id: "test-request",
          }, 409);
        }
        writeSucceeded = true;
        return jsonResponse({
          id: patientRecommendationFixture.id,
          author_id: patientRecommendationFixture.author.id,
          author_name: patientRecommendationFixture.author.display_name,
          text: "Мій уточнений текст",
          version: 3,
          created_at: patientRecommendationFixture.created_at,
          updated_at: "2026-07-21T11:00:00Z",
        });
      }
      if (/\/api\/v1\/visits\/[0-9a-f-]+\/recommendations\/[0-9a-f-]+$/.test(new URL(request.url).pathname)) {
        return jsonResponse({
          id: patientRecommendationFixture.id,
          author_id: patientRecommendationFixture.author.id,
          author_name: patientRecommendationFixture.author.display_name,
          text: "Актуальний серверний текст",
          version,
          created_at: patientRecommendationFixture.created_at,
          updated_at: "2026-07-21T10:30:00Z",
        });
      }
      if (writeSucceeded) {
        return jsonResponse({
          code: "service_unavailable",
          message: "Не вдалося повторно завантажити список.",
          fields: {},
          correlation_id: "test-request",
        }, 503);
      }
      return jsonResponse({
        ...patientRecommendationResponseFixture,
        recommendations: [{
          ...patientRecommendationFixture,
          text: version === 1 ? patientRecommendationFixture.text : "Актуальний серверний текст",
          version,
        }],
      });
    });
    render(<PatientRecommendationsTab patientId={patientFixture.id} />);
    await screen.findByText(patientRecommendationFixture.text);
    fireEvent.click(screen.getByRole("button", { name: "Редагувати" }));
    const dialog = screen.getByRole("dialog", { name: "Редагувати рекомендацію" });
    const textarea = within(dialog).getByLabelText("Рекомендація");
    fireEvent.change(textarea, { target: { value: "Мій уточнений текст" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Зберегти рекомендацію" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("ваш текст збережено у формі");
    expect(textarea).toHaveValue("Мій уточнений текст");
    fireEvent.click(within(dialog).getByRole("button", { name: "Зберегти рекомендацію" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Рекомендацію оновлено");
    expect(await screen.findByText("Мій уточнений текст")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("Не вдалося повторно завантажити список");
    expect(patchBodies).toEqual([
      { text: "Мій уточнений текст", version: 1 },
      { text: "Мій уточнений текст", version: 2 },
    ]);
  });
});
