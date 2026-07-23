import { mkdir } from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright-core";

const baseUrl = process.env.TP201_BASE_URL ?? "http://127.0.0.1:8088";
const edgePath = process.env.TP201_EDGE_PATH;
const receptionPassword = process.env.TP201_RECEPTION_PASSWORD;
const adminPassword = process.env.TP201_ADMIN_PASSWORD;

if (!edgePath || !receptionPassword || !adminPassword) {
  throw new Error("TP201_EDGE_PATH and local test passwords are required.");
}

const evidenceDir = path.resolve(process.cwd(), "../docs/evidence/tp-201");
await mkdir(evidenceDir, { recursive: true });

const browser = await chromium.launch({ executablePath: edgePath, headless: true });

async function loginViaApi(context, email, password) {
  await context.request.get(`${baseUrl}/api/v1/session`);
  const cookies = await context.cookies(baseUrl);
  const csrfCookie = cookies.find((cookie) => cookie.name === "podoria_csrftoken");
  if (!csrfCookie) {
    throw new Error("CSRF bootstrap cookie is missing.");
  }
  const response = await context.request.post(`${baseUrl}/api/v1/auth/login`, {
    data: { email, password },
    headers: { "X-CSRFToken": csrfCookie.value },
  });
  if (response.status() !== 200) {
    throw new Error(`Login API returned ${response.status()}: ${await response.text()}`);
  }
}

try {
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const desktopPage = await desktop.newPage();
  desktopPage.setDefaultTimeout(12_000);
  await desktopPage.goto(`${baseUrl}/inventory`);
  await desktopPage.getByRole("heading", { name: "Вхід до кабінету" }).waitFor();
  await desktopPage.screenshot({ path: path.join(evidenceDir, "login-desktop-1440x900.png") });

  await loginViaApi(desktop, "reception@podoria.local", receptionPassword);
  await desktopPage.goto(`${baseUrl}/inventory`);
  await desktopPage.getByRole("heading", { name: "Добрий день" }).waitFor();
  await desktopPage.getByRole("status").filter({ hasText: "Цей розділ недоступний" }).waitFor();
  if (await desktopPage.getByRole("link", { name: "Склад" }).count()) {
    throw new Error("Reception navigation exposes inventory.");
  }
  await desktopPage.screenshot({
    path: path.join(evidenceDir, "reception-direct-url-1440x900.png"),
  });

  await desktopPage.getByRole("button", { name: /Тест Рецепція/ }).click();
  await desktopPage.getByRole("menuitem", { name: "Вийти" }).click();
  await desktopPage.getByRole("heading", { name: "Вхід до кабінету" }).waitFor();
  await desktop.close();

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const mobilePage = await mobile.newPage();
  mobilePage.setDefaultTimeout(12_000);
  await mobilePage.goto(baseUrl);
  await mobilePage.getByRole("heading", { name: "Вхід до кабінету" }).waitFor();
  await loginViaApi(mobile, "admin@podoria.local", adminPassword);
  await mobilePage.goto(baseUrl);
  await mobilePage.getByRole("heading", { name: "Добрий день" }).waitFor();
  await mobilePage.getByRole("button", { name: "Ще" }).click();
  await mobilePage.getByRole("dialog", { name: "Тест Адміністратор" }).waitFor();
  await mobilePage.getByRole("link", { name: "Налаштування" }).waitFor();
  await mobilePage.screenshot({ path: path.join(evidenceDir, "admin-mobile-menu-390x844.png") });
  await mobile.close();

  console.log(JSON.stringify({ login: "ok", directUrl: "ok", logout: "ok", mobileAdmin: "ok" }));
} finally {
  await browser.close();
}
