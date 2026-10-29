import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

// Two renders in one file: the second finds only its own heading because test-setup.ts
// cleaned up the first.
function Heading() {
  return <h1>once</h1>;
}

test("a first render", () => {
  render(<Heading />);
  expect(screen.getAllByRole("heading")).toHaveLength(1);
});

test("a second render finds only its own heading", () => {
  render(<Heading />);
  expect(screen.getAllByRole("heading")).toHaveLength(1);
});
