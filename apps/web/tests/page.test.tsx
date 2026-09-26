import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import Home from "../app/page";

test("identifies the current milestone scope without claiming working financial flows", () => {
  render(<Home />);
  expect(
    screen.getByRole("heading", { name: "Receivable trust infrastructure" }),
  ).toBeVisible();
  expect(screen.getByText("Milestone 2 · Documents")).toBeVisible();
  expect(
    screen.getByText(/No live ledger or payment connection/),
  ).toBeVisible();
});
