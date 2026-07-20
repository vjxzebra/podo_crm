import axe from "axe-core";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { App } from "../App";

describe("application shell accessibility", () => {
  it.each(["/", "/previews/empty", "/previews/error", "/previews/forbidden", "/missing-route"])(
    "has no detectable accessibility violations at %s",
    async (path) => {
      const { container } = render(
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>,
      );

      await screen.findByTestId("desktop-sidebar");

      const results = await axe.run(container, {
        rules: {
          "color-contrast": { enabled: false },
        },
      });

      expect(results.violations).toEqual([]);
    },
  );
});
