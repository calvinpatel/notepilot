import { expect, test } from "vitest";

import { isEmpty, place, verdict } from "./findings";
import { claim, report, result } from "./test/builders";

test("a fired result naming two claims shows on both cards (§9.7)", () => {
  const fired = result({
    check: "allergy_contraindication",
    severity: "critical",
    passed: false,
    claim_ids: [0, 1],
  });
  const placed = place([claim({ id: 0 }), claim({ id: 1 })], report({ results: [fired] }));
  expect(placed.byClaim.get(0)).toEqual([fired]);
  expect(placed.byClaim.get(1)).toEqual([fired]);
  expect(placed.noteLevel).toEqual([]);
});

test("a fired result naming no claim goes to the banner", () => {
  const fired = result({ check: "allergy_preserved", severity: "critical", passed: false });
  const placed = place([claim({ id: 0 })], report({ results: [fired] }));
  expect(placed.noteLevel).toEqual([fired]);
  expect(placed.byClaim.size).toBe(0);
});

test("a fired result whose ids name no claim in the note goes to the banner, not nowhere", () => {
  const orphan = result({ check: "drug_in_quote", passed: false, claim_ids: [7] });
  const placed = place([claim({ id: 0 })], report({ results: [orphan] }));
  expect(placed.noteLevel).toEqual([orphan]);
  expect(placed.byClaim.size).toBe(0);
});

test("errored and passed results go by their own flags, never onto a card", () => {
  const errored = result({ check: "a", passed: false, errored: true, claim_ids: [0] });
  const passed = result({ check: "b", claim_ids: [0] });
  const placed = place([claim({ id: 0 })], report({ results: [errored, passed] }));
  expect(placed.errored).toEqual([errored]);
  expect(placed.passed).toEqual([passed]);
  expect(placed.byClaim.size).toBe(0);
  expect(placed.noteLevel).toEqual([]);
});

test("findings come critical first, on a card and in the banner", () => {
  const info = result({ check: "i", severity: "info", passed: false, claim_ids: [0] });
  const warning = result({ check: "w", severity: "warning", passed: false, claim_ids: [0] });
  const critical = result({ check: "c", severity: "critical", passed: false, claim_ids: [0] });
  const banner = [info, warning, critical].map((r) => ({ ...r, claim_ids: [] }));
  const results = [info, warning, critical, ...banner];
  const placed = place([claim({ id: 0 })], report({ results }));
  expect(placed.byClaim.get(0)?.map((r) => r.check)).toEqual(["c", "w", "i"]);
  expect(placed.noteLevel.map((r) => r.check)).toEqual(["c", "w", "i"]);
});

test("a result naming one claim twice shows on its card once", () => {
  const fired = result({ check: "x", passed: false, claim_ids: [0, 0] });
  expect(place([claim({ id: 0 })], report({ results: [fired] })).byClaim.get(0)).toEqual([fired]);
});

test("the verdict line counts what ran, the fired warnings, and what didn't run", () => {
  const results = [
    result({ check: "fired-warning", passed: false }),
    result({ check: "passed-warning" }),
    result({ check: "fired-critical", severity: "critical", passed: false }),
    result({ check: "errored-warning", passed: false, errored: true }),
  ];
  const checksRun = [...results.map((r) => r.check), "selected-without-a-result"];
  const counted = report({ results, checks_run: checksRun, all_critical_passed: false });
  expect(verdict(counted)).toEqual({
    allCriticalPassed: false,
    ran: 4,
    warnings: 1,
    didntRun: 1,
  });
});

test("the verdict is the report's, never recomputed (L102)", () => {
  const passing = report({ results: [result({ check: "a" })], all_critical_passed: false });
  expect(verdict(passing).allCriticalPassed).toBe(false);
});

test("an empty note whose results all passed is empty", () => {
  const passed = report({ results: [result({ check: "a" }), result({ check: "b" })] });
  expect(isEmpty([], passed)).toBe(true);
});

test.each([
  ["a claim", [claim({ id: 0 })], [result({ check: "a" })]],
  ["a fired warning", [], [result({ check: "empty_note", passed: false })]],
  ["an errored check", [], [result({ check: "a", passed: false, errored: true })]],
  ["no results at all", [], []],
])("a note with %s is not empty", (_name, claims, results) => {
  expect(isEmpty(claims, report({ results }))).toBe(false);
});
