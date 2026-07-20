import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("contract lab", () => {
  it("renders typed success and error fixtures", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Success fixture" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Error envelope" })).toBeInTheDocument();
    expect(screen.getByText(/tp102-story-success/)).toBeInTheDocument();
    expect(screen.getByText(/validation_error/)).toBeInTheDocument();
  });
});
