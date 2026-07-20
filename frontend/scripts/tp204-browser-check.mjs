import { mkdir } from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright-core";

const baseUrl = process.env.TP204_BASE_URL ?? "http://127.0.0.1:8088";
const edgePath = process.env.TP204_EDGE_PATH;
const adminPassword = process.env.TP204_ADMIN_PASSWORD;
const receptionPassword = process.env.TP204_RECEPTION_PASSWORD;

if (!edgePath || !adminPassword || !receptionPassword) {
  throw new Error("TP204_EDGE_PATH and local test passwords are required.");
}

const evidenceDir = path.resolve(process.cwd(), "../docs/evidence/tp-204");
await mkdir(evidenceDir, { recursive: true });
const browser = await chromium.launch({ executablePath: edgePath, headless: true });

async function csrfToken(context) {
  await context.request.get(`${baseUrl}/api/v1/session`);
  const cookies = await context.cookies(baseUrl);
  const csrfCookie = cookies.find((cookie) => cookie.name === "podoria_csrftoken");
  if (!csrfCookie) {
    throw new Error("CSRF bootstrap cookie is missing.");
  }
  return csrfCookie.value;
}

async function loginViaApi(context, email, password) {
  const response = await context.request.post(`${baseUrl}/api/v1/auth/login`, {
    data: { email, password },
    headers: { "X-CSRFToken": await csrfToken(context) },
  });
  if (response.status() !== 200) {
    throw new Error(`Login API returned ${response.status()}: ${await response.text()}`);
  }
  return response.json();
}

async function assertNoConsoleErrors(page, errors) {
  const fatal = errors.filter((message) => !message.includes("favicon"));
  if (fatal.length) {
    throw new Error(`Browser console errors: ${fatal.join(" | ")}`);
  }
  if ((await page.locator("body").evaluate((body) => body.scrollWidth > window.innerWidth))) {
    throw new Error("Page has horizontal overflow.");
  }
}

let failure = null;

try {
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const desktopPage = await desktop.newPage();
  const desktopErrors = [];
  desktopPage.on("console", (message) => {
    if (message.type() === "error") desktopErrors.push(message.text());
  });
  desktopPage.setDefaultTimeout(12_000);
  const adminSession = await loginViaApi(desktop, "tp204-admin@podoria.local", adminPassword);
  if (!adminSession.route_ids.includes("settings")) {
    throw new Error("Admin session does not expose the settings route.");
  }
  await desktopPage.goto(`${baseUrl}/settings`);
  await desktopPage.getByRole("heading", { name: "Налаштування кабінету" }).waitFor();
  await desktopPage.getByLabel("Назва кабінету").waitFor();
  for (const label of ["Назва кабінету", "Телефон", "Email", "Адреса"]) {
    if ((await desktopPage.getByLabel(label, { exact: true }).count()) !== 1) {
      throw new Error(`Missing singleton profile field: ${label}`);
    }
  }
  if ((await desktopPage.getByLabel("Короткий опис", { exact: false }).count()) !== 1) {
    throw new Error("Missing optional clinic description field.");
  }
  if (await desktopPage.getByText("Філія", { exact: true }).count()) {
    throw new Error("Branch controls must not exist in the one-location profile.");
  }
  await assertNoConsoleErrors(desktopPage, desktopErrors);
  await desktopPage.screenshot({ path: path.join(evidenceDir, "clinic-profile-1440x900.png") });
  await desktop.close();
  console.log("clinic-profile-desktop: ok");

  const tablet = await browser.newContext({ viewport: { width: 768, height: 1024 } });
  const tabletPage = await tablet.newPage();
  tabletPage.setDefaultTimeout(12_000);
  await loginViaApi(tablet, "tp204-admin@podoria.local", adminPassword);
  await tabletPage.goto(`${baseUrl}/settings`);
  await tabletPage.getByRole("heading", { name: "Налаштування кабінету" }).waitFor();
  await tabletPage.getByTestId("settings-rooms-tab").click();
  await tabletPage.getByRole("heading", { name: "Кімнати кабінету" }).waitFor();
  if ((await tabletPage.locator(".room-card").count()) < 1) {
    throw new Error("Expected the initial active room from ADR-001.");
  }
  await tabletPage.getByRole("button", { name: "Додати кімнату" }).click();
  await tabletPage.getByRole("dialog", { name: "Нова кімната" }).waitFor();
  await tabletPage.screenshot({ path: path.join(evidenceDir, "room-create-768x1024.png") });
  await tablet.close();
  console.log("room-create-tablet: ok");

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const mobilePage = await mobile.newPage();
  mobilePage.setDefaultTimeout(12_000);
  await loginViaApi(mobile, "tp204-admin@podoria.local", adminPassword);
  await mobilePage.goto(`${baseUrl}/settings`);
  await mobilePage.getByRole("heading", { name: "Налаштування кабінету" }).waitFor();
  await mobilePage.getByTestId("settings-rooms-tab").click();
  await mobilePage.getByRole("heading", { name: "Кімнати кабінету" }).waitFor();
  if (await mobilePage.locator("body").evaluate((body) => body.scrollWidth > window.innerWidth)) {
    throw new Error("Mobile room catalog has horizontal overflow.");
  }
  await mobilePage.screenshot({ path: path.join(evidenceDir, "room-catalog-390x844.png") });
  await mobile.close();
  console.log("room-catalog-mobile: ok");

  const reception = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const receptionPage = await reception.newPage();
  receptionPage.setDefaultTimeout(12_000);
  const receptionSession = await loginViaApi(
    reception,
    "tp204-reception@podoria.local",
    receptionPassword,
  );
  if (receptionSession.route_ids.includes("settings")) {
    throw new Error("Reception session unexpectedly exposes settings.");
  }
  await receptionPage.goto(`${baseUrl}/settings`);
  await receptionPage.getByRole("heading", { name: "Добрий день" }).waitFor();
  await receptionPage.getByRole("status").filter({ hasText: "Цей розділ недоступний" }).waitFor();
  if (await receptionPage.getByRole("link", { name: "Налаштування" }).count()) {
    throw new Error("Reception navigation exposes settings.");
  }
  await reception.close();
  console.log("reception-settings-boundary: ok");

  console.log(JSON.stringify({
    clinicProfile: "ok",
    roomCreateState: "ok",
    mobileRoomCatalog: "ok",
    receptionBoundary: "ok",
  }));
} catch (error) {
  failure = error;
  console.error(error);
} finally {
  await Promise.race([
    browser.close(),
    new Promise((resolve) => setTimeout(resolve, 3_000)),
  ]);
  process.exit(failure === null ? 0 : 1);
}
