import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { App } from "./App";
import { claim, jsonResponse, report, result, summarizeBody } from "./test/builders";

// The mask is one code point and two UTF-16 units, so a span after it sliced by unit would
// land one early (L177). "cough for 3 days" is code points 13 to 29.
const SENT = "😷 Pt reports cough for 3 days. Denies fever.";

type Body = ReturnType<typeof summarizeBody>;

function stubFetch(...responses: (Response | Error | Promise<Response>)[]) {
  const fetch = vi.fn<typeof globalThis.fetch>();
  for (const response of responses) {
    fetch.mockImplementationOnce(() =>
      response instanceof Error ? Promise.reject(response) : Promise.resolve(response),
    );
  }
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

function paste(text: string) {
  fireEvent.change(screen.getByLabelText("Paste a note to summarize"), {
    target: { value: text },
  });
  fireEvent.click(screen.getByRole("button", { name: "Summarize" }));
}

async function review(body: Body) {
  stubFetch(jsonResponse(200, body));
  render(<App />);
  paste(SENT);
  await screen.findByText("DRAFT — unverified");
}

function source() {
  return screen.getByRole("region", { name: "Source (as sent)" });
}

function marked(): HTMLElement | null {
  return source().querySelector("mark");
}

function sourceText() {
  return source().querySelector("pre")?.textContent;
}

function card(id: number) {
  return screen.getByRole("button", { name: new RegExp(`^#${String(id)} `) });
}

const GROUNDED = claim({ id: 0, text: "Cough for three days", source_span: [13, 29] });

function only(...claims: ReturnType<typeof claim>[]): Body {
  return summarizeBody({ note: { claims }, report: report({ results: [] }) });
}

test("the PHI banner stands above the paste box", () => {
  render(<App />);
  const banner = screen.getByRole("note");
  const box = screen.getByLabelText("Paste a note to summarize");
  expect(banner.textContent).toContain("not a HIPAA environment");
  expect(banner.compareDocumentPosition(box) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

test("the PHI banner stays in the review", async () => {
  await review(only(GROUNDED));
  expect(screen.getByRole("note").textContent).toContain("not a HIPAA environment");
});

test("the review shows the draft label, the verdict, the sections, and the receipt", async () => {
  await review(only(GROUNDED));
  expect(screen.getByText("All critical checks passed. · 0 ran")).toBeTruthy();
  for (const heading of ["Subjective", "Objective", "Assessment", "Plan"]) {
    expect(screen.getByRole("heading", { name: heading })).toBeTruthy();
  }
  expect(screen.getAllByText("none stated")).toHaveLength(2);
  expect(screen.getByText("No assessment documented")).toBeTruthy();
  const receipt = screen.getByText(/^claude-test · prompt 306bbaa5126a/);
  expect(receipt.textContent).toContain("1899 in / 797 out · note 6f1c2a9e-");
  expect(receipt.closest("a")).toBeNull(); // L58: the id names nothing to fetch
});

test("the button holds while a request is in flight, so a second click sends nothing", async () => {
  const fetch = stubFetch(new Promise<Response>(() => undefined));
  render(<App />);
  paste(SENT);
  const button = await screen.findByRole("button", { name: "Summarizing…" });
  fireEvent.click(button);
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(button.hasAttribute("disabled")).toBe(true);
  expect(screen.getByLabelText("Paste a note to summarize").hasAttribute("readonly")).toBe(true);
});

test("hovering a claim marks its span in the text as sent, by code point", async () => {
  await review(only(GROUNDED));
  expect(marked()).toBeNull();
  fireEvent.mouseEnter(card(0).closest("li") ?? card(0));
  expect(marked()?.textContent).toBe("cough for 3 days");
  expect(marked()?.className).toBe("grounded");
  expect(sourceText()).toBe(SENT);
});

test("leaving unmarks; focus marks; a click pins until clicked again", async () => {
  await review(only(GROUNDED));
  const item = card(0).closest("li") ?? card(0);
  fireEvent.mouseEnter(item);
  fireEvent.mouseLeave(item);
  expect(marked()).toBeNull();
  fireEvent.focus(card(0));
  expect(marked()?.textContent).toBe("cough for 3 days");
  fireEvent.blur(card(0));
  expect(marked()).toBeNull();
  fireEvent.click(card(0));
  expect(card(0).getAttribute("aria-pressed")).toBe("true");
  expect(marked()?.textContent).toBe("cough for 3 days");
  fireEvent.click(card(0));
  expect(card(0).getAttribute("aria-pressed")).toBe("false");
  expect(marked()).toBeNull();
});

test("one span is marked: the hovered claim's, else the focused, else the pinned", async () => {
  const fever = claim({ id: 1, text: "Denies fever", source_span: [31, 43] });
  await review(only(GROUNDED, fever));
  const cough = card(0).closest("li") ?? card(0);
  fireEvent.click(card(1));
  fireEvent.focus(card(0));
  expect(marked()?.textContent).toBe("cough for 3 days"); // focused over pinned
  fireEvent.mouseEnter(card(1).closest("li") ?? card(1));
  expect(marked()?.textContent).toBe("Denies fever"); // hovered over focused
  expect(source().querySelectorAll("mark")).toHaveLength(1);
  fireEvent.mouseLeave(card(1).closest("li") ?? card(1));
  expect(marked()?.textContent).toBe("cough for 3 days");
  fireEvent.blur(card(0));
  fireEvent.mouseLeave(cough);
  expect(marked()?.textContent).toBe("Denies fever"); // the pinned, alone
});

test("a paraphrased claim's span is marked yellow", async () => {
  await review(only({ ...GROUNDED, flags: ["paraphrased"] }));
  fireEvent.click(card(0));
  expect(marked()?.className).toBe("paraphrased");
  expect(screen.getByText("PARAPHRASED")).toBeTruthy();
});

test("a claim with no span marks nothing and says UNSUPPORTED", async () => {
  await review(only(claim({ id: 0, source_span: null, flags: ["unsupported"] })));
  fireEvent.click(card(0));
  expect(marked()).toBeNull();
  expect(screen.getByText("UNSUPPORTED")).toBeTruthy();
});

test("a span that doesn't fit the text as sent marks nothing", async () => {
  await review(only(claim({ id: 0, source_span: [40, 400] })));
  fireEvent.click(card(0));
  expect(marked()).toBeNull();
  expect(sourceText()).toBe(SENT);
});

test("findings go to cards and the banner, errored ones as not run, passed by name", async () => {
  const onCard = result({
    check: "drug_in_quote",
    severity: "critical",
    passed: false,
    claim_ids: [0],
  });
  const noteLevel = result({
    check: "allergy_preserved",
    severity: "critical",
    passed: false,
    detail: "penicillin",
  });
  const errored = result({ check: "laterality_consistency", passed: false, errored: true });
  const passed = result({ check: "med_status_consistency" });
  const results = [onCard, noteLevel, errored, passed];
  const failing = report({ results, all_critical_passed: false });
  await review(summarizeBody({ note: { claims: [GROUNDED] }, report: failing }));
  const banner = screen.getByRole("region", { name: "Note-level findings" });
  expect(within(banner).getByText(/allergy_preserved: penicillin/)).toBeTruthy();
  expect(within(banner).getByText("Didn't run on this note: laterality_consistency")).toBeTruthy();
  const item = card(0).closest("li") ?? card(0);
  // a finding with no detail ends at its check: no dangling colon
  expect(within(item).getByText(/drug_in_quote/).textContent).toBe("CRITICAL drug_in_quote");
  expect(screen.getByText("Passed (1): med_status_consistency")).toBeTruthy();
  expect(screen.getByText("Not all critical checks passed. · 3 ran · 1 didn't run")).toBeTruthy();
});

test("no note-level finding and nothing errored: no banner", async () => {
  await review(only(GROUNDED));
  expect(screen.queryByRole("region", { name: "Note-level findings" })).toBeNull();
});

test("markup in a claim or its quote renders as text", async () => {
  const markup = '<img src=x onerror="alert(1)">';
  await review(only(claim({ id: 0, text: markup, source_quote: markup })));
  expect(document.querySelector("img")).toBeNull();
  expect(screen.getAllByText(markup, { exact: false })).not.toHaveLength(0);
});

test("an error says its status, code, and request id, and keeps the draft", async () => {
  stubFetch(jsonResponse(503, { error: "budget_exhausted", request_id: "r2" }));
  render(<App />);
  paste(SENT);
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toBe("The request failed: HTTP 503 · budget_exhausted · request r2");
  expect(screen.getByLabelText("Paste a note to summarize")).toHaveProperty("value", SENT);
});

test("a body that isn't ours says its status alone, and no response says so", async () => {
  stubFetch(jsonResponse(502, "<html>Bad Gateway</html>"), new TypeError("network down"));
  render(<App />);
  paste(SENT);
  expect((await screen.findByRole("alert")).textContent).toBe("The request failed: HTTP 502");
  fireEvent.click(screen.getByRole("button", { name: "Summarize" }));
  expect(await screen.findByText("No response from the server.")).toBeTruthy();
});

test("New paste returns to the box with the text kept", async () => {
  await review(only(GROUNDED));
  fireEvent.click(screen.getByRole("button", { name: "New paste" }));
  expect(screen.getByLabelText("Paste a note to summarize")).toHaveProperty("value", SENT);
});
