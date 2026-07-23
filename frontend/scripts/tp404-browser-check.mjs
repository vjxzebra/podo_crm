import { mkdir } from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright-core";

const baseUrl = process.env.TP404_BASE_URL ?? "http://127.0.0.1:8088";
const edgePath = process.env.TP404_EDGE_PATH;
const adminEmail = process.env.PODORIA_LOCAL_ADMIN_EMAIL;
const adminPassword = process.env.PODORIA_LOCAL_ADMIN_PASSWORD;

if (!edgePath || !adminEmail || !adminPassword) {
  throw new Error(
    "TP404_EDGE_PATH, PODORIA_LOCAL_ADMIN_EMAIL and PODORIA_LOCAL_ADMIN_PASSWORD are required.",
  );
}

const evidenceDir = path.resolve(process.cwd(), "../docs/evidence/tp-404");
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
    throw new Error(`Login API returned ${response.status()}: ${await response.text()}`);
  }
  const session = await response.json();
  if (!session.route_ids.includes("calendar")) {
    throw new Error("Admin calendar route is missing.");
  }
}

async function calendarPage(viewport) {
  const context = await browser.newContext({ viewport });
  await loginViaApi(context);
  const page = await context.newPage();
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  page.setDefaultTimeout(12_000);
  await page.goto(`${baseUrl}/calendar`);
  await page.getByRole("heading", { name: "Розклад клініки" }).waitFor();
  const events = page.getByTestId("calendar-event");
  await events.first().waitFor();
  if (await events.count() !== 2) throw new Error("Expected two calendar events.");
  return { context, errors, page };
}

async function readDayMetrics(page) {
  return page.locator(".calendar-day__scroll").evaluate((scroller) => {
    const rect = (element) => {
      const bounds = element.getBoundingClientRect();
      return {
        bottom: bounds.bottom,
        height: bounds.height,
        left: bounds.left,
        right: bounds.right,
        top: bounds.top,
        width: bounds.width,
      };
    };
    const events = Array.from(document.querySelectorAll("[data-testid='calendar-event']"))
      .map((event) => ({
        ...rect(event),
        clientHeight: event.clientHeight,
        clientWidth: event.clientWidth,
        scrollHeight: event.scrollHeight,
        scrollWidth: event.scrollWidth,
      }));
    const overlaps = events.flatMap((left, index) => events.slice(index + 1).map((right) => (
      left.left < right.right
      && left.right > right.left
      && left.top < right.bottom
      && left.bottom > right.top
    ))).filter(Boolean);
    const freeSlots = Array.from(document.querySelectorAll(".calendar-slot--free"));
    const controls = Array.from(document.querySelectorAll(
      ".calendar-toolbar button, .calendar-toolbar select, .calendar-heading__actions .button",
    ));
    return {
      activeElementIsScroller: document.activeElement === scroller,
      ariaDescribedBy: scroller.getAttribute("aria-describedby"),
      ariaLabel: scroller.getAttribute("aria-label"),
      clientHeight: scroller.clientHeight,
      clientWidth: scroller.clientWidth,
      controlMinHeight: Math.min(...controls.map((control) => control.getBoundingClientRect().height)),
      eventCount: events.length,
      eventTextClipped: events.some((event) => (
        event.scrollWidth > event.clientWidth + 1 || event.scrollHeight > event.clientHeight + 1
      )),
      events,
      freeSlotMinHeight: Math.min(...freeSlots.map((slot) => slot.getBoundingClientRect().height)),
      overlaps: overlaps.length,
      pageClientWidth: document.documentElement.clientWidth,
      pageScrollWidth: document.documentElement.scrollWidth,
      scrollHeight: scroller.scrollHeight,
      scrollLeft: scroller.scrollLeft,
      scrollWidth: scroller.scrollWidth,
      tabIndex: scroller.tabIndex,
    };
  });
}

function assertDayMetrics(name, metrics, minimumTargetHeight, requiresHorizontalScroll) {
  if (metrics.pageScrollWidth > metrics.pageClientWidth) {
    throw new Error(`${name} page overflow: ${JSON.stringify(metrics)}`);
  }
  if (requiresHorizontalScroll && metrics.scrollWidth <= metrics.clientWidth) {
    throw new Error(`${name} specialist grid is not internally scrollable.`);
  }
  if (metrics.eventCount !== 2 || metrics.overlaps !== 0 || metrics.eventTextClipped) {
    throw new Error(`${name} concurrent event layout failed: ${JSON.stringify(metrics)}`);
  }
  if (metrics.events[0]?.top !== metrics.events[1]?.top) {
    throw new Error(`${name} concurrent events do not share a start row.`);
  }
  if (metrics.events[0]?.left === metrics.events[1]?.left) {
    throw new Error(`${name} concurrent events share a specialist column.`);
  }
  if (metrics.tabIndex !== 0 || !metrics.ariaLabel || !metrics.ariaDescribedBy) {
    throw new Error(`${name} scroller is missing keyboard semantics.`);
  }
  if (
    metrics.freeSlotMinHeight < minimumTargetHeight
    || metrics.controlMinHeight < minimumTargetHeight
  ) {
    throw new Error(`${name} touch target is too small: ${JSON.stringify(metrics)}`);
  }
}

async function assertNoErrors(name, errors) {
  if (errors.length > 0) {
    throw new Error(`${name} browser errors: ${errors.join(" | ")}`);
  }
}

async function runDayGate(
  name,
  viewport,
  minimumTargetHeight,
  screenshotName,
  requiresHorizontalScroll,
  checksDialogFocus,
) {
  const result = await calendarPage(viewport);
  const scroller = result.page.getByTestId("calendar-day-scroll");
  await scroller.focus();
  const beforeKeyboard = await readDayMetrics(result.page);
  await scroller.press("ArrowRight");
  await result.page.waitForTimeout(150);
  const afterKeyboard = await readDayMetrics(result.page);
  assertDayMetrics(name, afterKeyboard, minimumTargetHeight, requiresHorizontalScroll);
  if (
    !afterKeyboard.activeElementIsScroller
    || (requiresHorizontalScroll && afterKeyboard.scrollLeft <= beforeKeyboard.scrollLeft)
  ) {
    throw new Error(`${name} keyboard scrolling failed: ${JSON.stringify(afterKeyboard)}`);
  }
  let focusLifecycle = null;
  if (checksDialogFocus) {
    const events = result.page.getByTestId("calendar-event");
    const firstEvent = events.first();
    const eventLabel = await firstEvent.getAttribute("aria-label");
    await firstEvent.focus();
    await firstEvent.press("Enter");
    const close = result.page.getByRole("button", { name: "Закрити деталі запису" });
    await close.waitFor();
    const dialogFocus = await close.evaluate((element) => document.activeElement === element);
    if (!dialogFocus) throw new Error(`${name} dialog did not receive focus.`);
    await close.click();
    await result.page.getByRole("dialog", { name: "Деталі запису" }).waitFor({ state: "detached" });
    await result.page.waitForTimeout(50);
    const returnedLabel = await result.page.evaluate(
      () => document.activeElement?.getAttribute("aria-label") ?? null,
    );
    if (returnedLabel !== eventLabel) {
      throw new Error(`${name} focus did not return to the invoking event.`);
    }
    focusLifecycle = { dialogFocus, eventLabel, returnedLabel };
  }
  await scroller.evaluate((element) => {
    element.scrollLeft = Math.min(
      element.scrollWidth - element.clientWidth,
      Math.max(0, element.scrollWidth - element.clientWidth - 2),
    );
  });
  await result.page.screenshot({
    fullPage: false,
    path: path.join(evidenceDir, screenshotName),
  });
  await assertNoErrors(name, result.errors);
  console.log(`${name}: ${JSON.stringify({ ...afterKeyboard, focusLifecycle })}`);
  return result;
}

let failure = null;

try {
  const desktop = await runDayGate(
    "desktop",
    { width: 1440, height: 900 },
    24,
    "calendar-desktop-1440x900.png",
    false,
    true,
  );
  await desktop.context.close();

  const tablet = await runDayGate(
    "tablet",
    { width: 768, height: 1024 },
    44,
    "calendar-tablet-768x1024.png",
    true,
    false,
  );
  await tablet.context.close();

  const mobile = await runDayGate(
    "mobile",
    { width: 390, height: 844 },
    44,
    "calendar-mobile-390x844.png",
    true,
    false,
  );
  const weekButton = mobile.page.getByRole("button", { name: "Тиждень" });
  await weekButton.click();
  const weekScroller = mobile.page.getByTestId("calendar-week-scroll");
  await weekScroller.waitFor();
  const weekMetrics = await weekScroller.evaluate((scroller) => ({
    ariaDescribedBy: scroller.getAttribute("aria-describedby"),
    ariaLabel: scroller.getAttribute("aria-label"),
    clientWidth: scroller.clientWidth,
    pageClientWidth: document.documentElement.clientWidth,
    pageScrollWidth: document.documentElement.scrollWidth,
    scrollWidth: scroller.scrollWidth,
    tabIndex: scroller.tabIndex,
  }));
  if (
    weekMetrics.pageScrollWidth > weekMetrics.pageClientWidth
    || weekMetrics.scrollWidth <= weekMetrics.clientWidth
    || weekMetrics.tabIndex !== 0
    || !weekMetrics.ariaLabel
    || !weekMetrics.ariaDescribedBy
  ) {
    throw new Error(`Mobile week layout failed: ${JSON.stringify(weekMetrics)}`);
  }
  await mobile.page.screenshot({
    fullPage: false,
    path: path.join(evidenceDir, "calendar-week-mobile-390x844.png"),
  });
  await assertNoErrors("mobile week", mobile.errors);
  await mobile.context.close();
  console.log(`mobile-week: ${JSON.stringify(weekMetrics)}`);
} catch (error) {
  failure = error;
  console.error(error);
} finally {
  await Promise.race([browser.close(), new Promise((resolve) => setTimeout(resolve, 3_000))]);
  process.exit(failure === null ? 0 : 1);
}
