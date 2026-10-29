import { expect, test, vi } from "vitest";

import { summarize } from "./client";
import { claim, jsonResponse, report, summarizeBody } from "./test/builders";

function stubFetch(response: Response | Error) {
  const fetch = vi.fn<typeof globalThis.fetch>(() =>
    response instanceof Error ? Promise.reject(response) : Promise.resolve(response),
  );
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

test("it POSTs the paste as JSON to the origin that served the page", async () => {
  const fetch = stubFetch(jsonResponse(422, { error: "input_invalid", request_id: "r1" }));
  await summarize("Pt reports cough.");
  expect(fetch).toHaveBeenCalledWith("/summarize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_text: "Pt reports cough." }),
  });
});

test("VITE_API_BASE points the dev server at the API's origin", async () => {
  vi.stubEnv("VITE_API_BASE", "http://localhost:8000");
  const fetch = stubFetch(jsonResponse(422, { error: "input_invalid", request_id: "r1" }));
  await summarize("Pt reports cough.");
  expect(fetch.mock.calls[0]?.[0]).toBe("http://localhost:8000/summarize");
});

test("a 200 is the result", async () => {
  const note = { claims: [claim({ id: 0 })] };
  const body = summarizeBody({ note, report: report({ results: [] }) });
  stubFetch(jsonResponse(200, body));
  expect(await summarize("x")).toEqual({ kind: "result", body });
});

test("an error in §9.4's shape keeps its status, code, and request id", async () => {
  stubFetch(jsonResponse(503, { error: "budget_exhausted", request_id: "r2" }));
  expect(await summarize("x")).toEqual({
    kind: "error",
    status: 503,
    code: "budget_exhausted",
    requestId: "r2",
  });
});

test.each([
  ["an HTML page", 502, "<html>Bad Gateway</html>"],
  ["fields of the wrong type", 422, { error: 1, request_id: "r3" }],
  ["a code without a request id", 500, { error: "internal_error" }],
  ["a request id that isn't a string", 503, { error: "budget_exhausted", request_id: 7 }],
  ["a 200 that isn't JSON", 200, "<html>proxy</html>"],
  ["a 2xx other than 200", 201, { note_id: "n" }],
])("%s keeps its status alone", async (_name, status, body) => {
  stubFetch(jsonResponse(status, body));
  expect(await summarize("x")).toEqual({ kind: "error", status, code: null, requestId: null });
});

test("a fetch that gets no response is no response", async () => {
  stubFetch(new TypeError("network down"));
  expect(await summarize("x")).toEqual({ kind: "no-response" });
});
