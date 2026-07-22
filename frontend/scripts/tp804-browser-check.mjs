import { mkdir } from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright-core";

const baseUrl = process.env.TP804_BASE_URL ?? "http://127.0.0.1:8088";
const edgePath = process.env.TP804_EDGE_PATH;
const adminEmail = process.env.PODORIA_LOCAL_ADMIN_EMAIL;
const adminPassword = process.env.PODORIA_LOCAL_ADMIN_PASSWORD;

if (!edgePath || !adminEmail || !adminPassword) {
  throw new Error(
    "TP804_EDGE_PATH, PODORIA_LOCAL_ADMIN_EMAIL and PODORIA_LOCAL_ADMIN_PASSWORD are required.",
  );
}

const evidenceDir = path.resolve(process.cwd(), "../docs/evidence/tp-804");
await mkdir(evidenceDir, { recursive: true });
const browser = await chromium.launch({ executablePath: edgePath, headless: true });

async function csrfToken(context) {
  await context.request.get(`${baseUrl}/api/v1/session`);
  const cookies = await context.cookies(baseUrl);
  const csrfCookie = cookies.find((cookie) => cookie.name === "podoria_csrftoken");
  if (!csrfCookie) throw new Error("CSRF bootstrap cookie is missing.");
  return csrfCookie.value;
}

async function loginViaApi(context) {
  const response = await context.request.post(`${baseUrl}/api/v1/auth/login`, {
    data: { email: adminEmail, password: adminPassword },
    headers: { "X-CSRFToken": await csrfToken(context) },
  });
  if (response.status() !== 200) {
    throw new Error(`Login API returned ${response.status()}.`);
  }
  const session = await response.json();
  if (!session.route_ids.includes("overview") || !session.route_ids.includes("analytics")) {
    throw new Error("Admin session is missing overview or analytics routes.");
  }
}

function columnCount(value) {
  return value === "none" ? 0 : value.trim().split(/\s+/).length;
}

async function openPage(viewport, route, heading) {
  const context = await browser.newContext({ viewport });
  await loginViaApi(context);
  const page = await context.newPage();
  const errors = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  page.setDefaultTimeout(12_000);
  await page.goto(`${baseUrl}${route}`);
  await page.getByRole("heading", { name: heading, exact: true }).waitFor();
  return { context, errors, page };
}

async function layoutMetrics(page, selectors) {
  return page.locator("main").evaluate((_, selected) => {
    const styles = Object.fromEntries(selected.map((selector) => {
      const element = document.querySelector(selector);
      if (!element) throw new Error(`Missing layout selector: ${selector}`);
      return [selector, getComputedStyle(element)];
    }));
    return {
      clientWidth: document.documentElement.clientWidth,
      gridColumns: Object.fromEntries(selected.map((selector) => [
        selector,
        styles[selector].gridTemplateColumns,
      ])),
      mobileNavDisplay: getComputedStyle(document.querySelector(".mobile-bottom-nav")).display,
      scrollWidth: document.documentElement.scrollWidth,
      sidebarDisplay: getComputedStyle(document.querySelector(".sidebar")).display,
    };
  }, selectors);
}

function assertLayout(name, metrics, expectedColumns, expectMobileShell) {
  if (metrics.scrollWidth > metrics.clientWidth) {
    throw new Error(`${name} page overflow: ${JSON.stringify(metrics)}`);
  }
  for (const [selector, expected] of Object.entries(expectedColumns)) {
    const actual = columnCount(metrics.gridColumns[selector]);
    if (actual !== expected) {
      throw new Error(`${name} ${selector} columns ${actual}, expected ${expected}.`);
    }
  }
  if (expectMobileShell) {
    if (metrics.sidebarDisplay !== "none" || metrics.mobileNavDisplay === "none") {
      throw new Error(`${name} mobile shell is not active: ${JSON.stringify(metrics)}`);
    }
  } else if (metrics.sidebarDisplay === "none" || metrics.mobileNavDisplay !== "none") {
    throw new Error(`${name} desktop/tablet shell is not active: ${JSON.stringify(metrics)}`);
  }
}

function assertNoErrors(name, errors) {
  if (errors.length > 0) throw new Error(`${name} browser errors: ${errors.join(" | ")}`);
}

const viewports = [
  {
    name: "desktop",
    viewport: { width: 1440, height: 900 },
    overviewColumns: 4,
    analyticsColumns: { filters: 4, kpis: 3, main: 2 },
    mobile: false,
  },
  {
    name: "tablet",
    viewport: { width: 1024, height: 768 },
    overviewColumns: 2,
    analyticsColumns: { filters: 4, kpis: 3, main: 2 },
    mobile: false,
  },
  {
    name: "mobile",
    viewport: { width: 390, height: 844 },
    overviewColumns: 2,
    analyticsColumns: { filters: 1, kpis: 1, main: 1 },
    mobile: true,
  },
];

try {
  for (const config of viewports) {
    const overview = await openPage(config.viewport, "/", "Добрий день");
    try {
      await overview.page.getByRole("region", { name: "Ключові показники" }).waitFor();
      await overview.page.getByRole("heading", { name: /\d+ із \d+ виконано/ }).waitFor();
      const metrics = await layoutMetrics(overview.page, [".stats-grid"]);
      assertLayout(
        `${config.name} overview`,
        metrics,
        { ".stats-grid": config.overviewColumns },
        config.mobile,
      );
      await overview.page.screenshot({
        fullPage: true,
        path: path.join(evidenceDir, `overview-${config.name}.png`),
      });
      assertNoErrors(`${config.name} overview`, overview.errors);
    } finally {
      await overview.context.close();
    }

    const analytics = await openPage(config.viewport, "/analytics", "Аналітика клініки");
    try {
      await analytics.page.getByRole("region", { name: "Ключові показники аналітики" }).waitFor();
      if (await analytics.page.locator(".analytics-kpi").count() !== 6) {
        throw new Error(`${config.name} analytics does not render six KPIs.`);
      }
      const quarter = analytics.page.getByRole("button", { name: "Квартал", exact: true });
      await Promise.all([
        analytics.page.waitForResponse((response) => (
          response.url().includes("/api/v1/analytics?") && response.status() === 200
        )),
        quarter.click(),
      ]);
      const toValue = await analytics.page.getByLabel("До", { exact: true }).inputValue();
      if (toValue !== "2026-09-30") {
        throw new Error(`${config.name} quarter end is ${toValue}, expected 2026-09-30.`);
      }
      if (await quarter.getAttribute("aria-pressed") !== "true") {
        throw new Error(`${config.name} quarter filter is not pressed.`);
      }
      if (await analytics.page.getByText("Експорт", { exact: false }).count() !== 0) {
        throw new Error(`${config.name} analytics renders an unapproved export action.`);
      }
      const metrics = await layoutMetrics(analytics.page, [
        ".analytics-filter-grid",
        ".analytics-kpis",
        ".analytics-main-grid",
      ]);
      assertLayout(
        `${config.name} analytics`,
        metrics,
        {
          ".analytics-filter-grid": config.analyticsColumns.filters,
          ".analytics-kpis": config.analyticsColumns.kpis,
          ".analytics-main-grid": config.analyticsColumns.main,
        },
        config.mobile,
      );
      await analytics.page.screenshot({
        fullPage: true,
        path: path.join(evidenceDir, `analytics-${config.name}.png`),
      });
      assertNoErrors(`${config.name} analytics`, analytics.errors);
    } finally {
      await analytics.context.close();
    }
  }
  console.log("TP-804 authenticated responsive browser gate passed.");
} finally {
  await Promise.race([
    browser.close(),
    new Promise((resolve) => setTimeout(resolve, 3_000)),
  ]);
  setTimeout(() => process.exit(process.exitCode ?? 0), 500);
}
