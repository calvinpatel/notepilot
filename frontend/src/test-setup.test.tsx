import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

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

// A stubbed fetch and a stubbed environment end with their test: the next test in the file
// sees neither.
const stubbedFetch = vi.fn<typeof globalThis.fetch>();

test("a test stubs fetch and VITE_API_BASE", () => {
  vi.stubGlobal("fetch", stubbedFetch);
  vi.stubEnv("VITE_API_BASE", "http://localhost:8000");
  expect(globalThis.fetch).toBe(stubbedFetch);
});

test("the next test sees neither stub", () => {
  expect(globalThis.fetch).not.toBe(stubbedFetch);
  expect(import.meta.env.VITE_API_BASE).toBeUndefined();
});
