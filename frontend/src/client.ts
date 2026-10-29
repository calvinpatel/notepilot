import type { components } from "./api";

export type SummarizeResponse = components["schemas"]["SummarizeResponse"];

/** What a summarize request came back with (§9.4, §9.10). */
export type Outcome =
  | { readonly kind: "result"; readonly body: SummarizeResponse }
  | {
      readonly kind: "error";
      readonly status: number;
      readonly code: string | null;
      readonly requestId: string | null;
      /** Retry-After's whole seconds, when it carries them (§9.8). */
      readonly retryAfter: number | null;
    }
  | { readonly kind: "no-response" };

/** The body's code and request id, when it carries both as strings (§9.4's one shape). */
function errorFields(body: unknown): { code: string; requestId: string } | null {
  if (typeof body === "object" && body !== null && "error" in body && "request_id" in body) {
    const { error, request_id: requestId } = body;
    if (typeof error === "string" && typeof requestId === "string") {
      return { code: error, requestId };
    }
  }
  return null;
}

function retryAfter(response: Response): number | null {
  const value = response.headers.get("Retry-After");
  return value !== null && /^\d+$/.test(value) ? Number(value) : null;
}

/**
 * POST the paste to /summarize (L362). A 200's JSON is typed by the schema the API serves
 * (§9.10, L357) and not checked again here; a 200 that isn't JSON, and any other status,
 * 2xx included, come back as an error, with the code and request id when the body carries
 * both.
 */
export async function summarize(rawText: string): Promise<Outcome> {
  const base = import.meta.env.VITE_API_BASE ?? "";
  let response: Response;
  try {
    response = await fetch(`${base}/summarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_text: rawText }),
    });
  } catch {
    return { kind: "no-response" };
  }
  if (response.status === 200) {
    let body: SummarizeResponse;
    try {
      body = await response.json();
    } catch {
      const status = response.status;
      return { kind: "error", status, code: null, requestId: null, retryAfter: null };
    }
    return { kind: "result", body };
  }
  let json: unknown = null;
  try {
    json = await response.json();
  } catch {
    json = null;
  }
  const fields = errorFields(json);
  return {
    kind: "error",
    status: response.status,
    code: fields?.code ?? null,
    requestId: fields?.requestId ?? null,
    retryAfter: retryAfter(response),
  };
}
