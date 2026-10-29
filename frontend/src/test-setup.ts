import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// Testing Library unmounts after each test only through a global afterEach, which Vitest
// defines only with globals on; without this, a second render in one file finds the first.
// A test's stubbed fetch and environment go with it.
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
