import { mkdir } from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright-core";

const baseUrl = process.env.TP205_BASE_URL ?? "http://127.0.0.1:8088";
const edgePath = process.env.TP205_EDGE_PATH;
const adminPassword = process.env.TP205_ADMIN_PASSWORD;
const receptionPassword = process.env.TP205_RECEPTION_PASSWORD;

if (!edgePath || !adminPassword || !receptionPassword) {
  throw new Error("TP205_EDGE_PATH and local test passwords are required.");
}

const evidenceDir = path.resolve(process.cwd(), "../docs/evidence/tp-205");
await mkdir(evidenceDir, { recursive: true });
const browser = await chromium.launch({ executablePath: edgePath, headless: true });

async function csrfToken(context) {
  await context.request.get(`${baseUrl}/api/v1/session`);
  const cookies = await context.cookies(baseUrl);
  const csrfCookie = cookies.find((cookie) => cookie.name === "podoria_csrftoken");
  if (!csrfCookie) throw new Error("CSRF bootstrap cookie is missing.");
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

async function assertHealthyPage(page, errors) {
  const fatal = errors.filter((message) => !message.includes("favicon"));
  if (fatal.length) throw new Error(`Browser console errors: ${fatal.join(" | ")}`);
  const overflow = await page.locator("body").evaluate((body) => ({
    scrollWidth: body.scrollWidth,
    viewportWidth: window.innerWidth,
    culprits: [...body.querySelectorAll("*")]
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        return rect.right > window.innerWidth + 1 || rect.left < -1;
      })
      .slice(0, 5)
      .map((element) => ({
        className: element.className,
        left: Math.round(element.getBoundingClientRect().left),
        right: Math.round(element.getBoundingClientRect().right),
        tagName: element.tagName,
      })),
  }));
  if (overflow.scrollWidth > overflow.viewportWidth) {
    throw new Error(`Page has horizontal overflow: ${JSON.stringify(overflow)}`);
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
  const adminSession = await loginViaApi(desktop, "tp205-admin@podoria.local", adminPassword);
  if (!adminSession.route_ids.includes("settings")) throw new Error("Admin settings route is missing.");
  await desktopPage.goto(`${baseUrl}/settings`);
  await desktopPage.getByRole("heading", { name: "Налаштування кабінету" }).waitFor();
  await desktopPage.getByTestId("settings-services-tab").click();
  await desktopPage.getByRole("heading", { name: "Послуги кабінету" }).waitFor();
  await desktopPage.getByText("Первинна консультація", { exact: true }).waitFor();
  if ((await desktopPage.locator(".service-row").count()) !== 5) {
    throw new Error("Expected five TP-205 service fixtures.");
  }
  if ((await desktopPage.locator(".service-row--inactive").count()) !== 1) {
    throw new Error("Inactive service state is missing.");
  }
  if ((await desktopPage.locator(".service-color").count()) !== 5) {
    throw new Error("Calendar color markers are missing.");
  }
  await assertHealthyPage(desktopPage, desktopErrors);
  await desktopPage.screenshot({ path: path.join(evidenceDir, "service-catalog-1440x900.png") });
  await desktopPage.getByLabel("Пошук", { exact: true }).fill("мозоля");
  if ((await desktopPage.locator(".service-row").count()) !== 1) {
    throw new Error("Service search did not narrow the catalog.");
  }
  await desktopPage.getByLabel("Скинути фільтри").click();
  await desktop.close();
  console.log("service-catalog-desktop: ok");

  const tablet = await browser.newContext({ viewport: { width: 768, height: 1024 } });
  const tabletPage = await tablet.newPage();
  const tabletErrors = [];
  tabletPage.on("console", (message) => {
    if (message.type() === "error") tabletErrors.push(message.text());
  });
  tabletPage.setDefaultTimeout(12_000);
  await loginViaApi(tablet, "tp205-admin@podoria.local", adminPassword);
  await tabletPage.goto(`${baseUrl}/settings`);
  await tabletPage.getByRole("heading", { name: "Налаштування кабінету" }).waitFor();
  await tabletPage.getByTestId("settings-services-tab").click();
  await tabletPage.getByRole("heading", { name: "Послуги кабінету" }).waitFor();
  await tabletPage.getByRole("button", { name: "Додати послугу" }).click();
  const createDialog = tabletPage.getByRole("dialog", { name: "Нова послуга" });
  await createDialog.waitFor();
  if ((await createDialog.locator("input[type=radio]").count()) !== 8) {
    throw new Error("Expected eight accessible calendar palette colors.");
  }
  for (const label of ["Код послуги", "Назва", "Тривалість, хв", "Ціна, ₴"]) {
    if ((await createDialog.getByLabel(label, { exact: true }).count()) !== 1) {
      throw new Error(`Missing service editor field: ${label}`);
    }
  }
  await tabletPage.screenshot({ path: path.join(evidenceDir, "service-create-palette-768x1024.png") });
  await assertHealthyPage(tabletPage, tabletErrors);
  await tablet.close();
  console.log("service-create-tablet: ok");

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const mobilePage = await mobile.newPage();
  const mobileErrors = [];
  mobilePage.on("console", (message) => {
    if (message.type() === "error") mobileErrors.push(message.text());
  });
  mobilePage.setDefaultTimeout(12_000);
  await loginViaApi(mobile, "tp205-admin@podoria.local", adminPassword);
  await mobilePage.goto(`${baseUrl}/settings`);
  await mobilePage.getByRole("heading", { name: "Налаштування кабінету" }).waitFor();
  await mobilePage.getByTestId("settings-services-tab").click();
  await mobilePage.getByRole("heading", { name: "Послуги кабінету" }).waitFor();
  await mobilePage.getByText("Первинна консультація", { exact: true }).waitFor();
  if ((await mobilePage.locator(".service-row").count()) !== 5) {
    throw new Error("Mobile service cards are incomplete.");
  }
  await assertHealthyPage(mobilePage, mobileErrors);
  await mobilePage.locator(".service-table").scrollIntoViewIfNeeded();
  await mobilePage.screenshot({ path: path.join(evidenceDir, "service-cards-390x844.png") });
  await mobile.close();
  console.log("service-cards-mobile: ok");

  const reception = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const receptionPage = await reception.newPage();
  receptionPage.setDefaultTimeout(12_000);
  const receptionSession = await loginViaApi(
    reception,
    "tp205-reception@podoria.local",
    receptionPassword,
  );
  if (receptionSession.route_ids.includes("settings")) {
    throw new Error("Reception session unexpectedly exposes settings.");
  }
  const pickerResponse = await reception.request.get(`${baseUrl}/api/v1/services`);
  const picker = await pickerResponse.json();
  if (pickerResponse.status() !== 200 || picker.services.length !== 4) {
    throw new Error("Reception active-service picker projection is incorrect.");
  }
  const expectedPickerKeys = ["code", "color", "duration_minutes", "id", "name", "price_minor"];
  if (JSON.stringify(Object.keys(picker.services[0]).sort()) !== JSON.stringify(expectedPickerKeys)) {
    throw new Error("Reception picker exposes administrator-only fields.");
  }
  await receptionPage.goto(`${baseUrl}/settings`);
  await receptionPage.getByRole("heading", { name: "Добрий день" }).waitFor();
  await receptionPage.getByRole("status").filter({ hasText: "Цей розділ недоступний" }).waitFor();
  await reception.close();
  console.log("reception-picker-boundary: ok");

  console.log(JSON.stringify({
    desktopCatalog: "ok",
    tabletPalette: "ok",
    mobileCards: "ok",
    receptionPickerBoundary: "ok",
  }));
} catch (error) {
  failure = error;
  console.error(error);
} finally {
  await Promise.race([browser.close(), new Promise((resolve) => setTimeout(resolve, 3_000))]);
  process.exit(failure === null ? 0 : 1);
}
