import axe from "axe-core";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { App } from "../App";

describe("application shell accessibility", () => {
  it.each(["/", "/patients", "/patients/c49d72c2-689d-4f54-91df-9a63845a02e7/overview", "/work-items", "/team", "/settings", "/previews/empty", "/previews/error", "/previews/forbidden", "/missing-route"])(
    "has no detectable accessibility violations at %s",
    async (path) => {
      const { container } = render(
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>,
      );

      await screen.findByTestId("desktop-sidebar");
      if (path === "/team") {
        await screen.findByText("Працівників не знайдено");
      }
      if (path === "/patients") {
        await screen.findByText("Марія Бондар");
      }
      if (path.startsWith("/patients/")) {
        await screen.findByRole("heading", { name: "Марія Бондар", level: 1 });
      }
      if (path === "/work-items") {
        await screen.findByText("Уточнити самопочуття після візиту");
      }
      if (path === "/settings") {
        await screen.findByRole("heading", { name: "Профіль кабінету" });
      }

      const results = await axe.run(container, {
        rules: {
          "color-contrast": { enabled: false },
        },
      });

      expect(results.violations).toEqual([]);
    },
  );
});
