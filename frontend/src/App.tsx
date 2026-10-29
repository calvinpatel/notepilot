import { useState } from "react";

import { type Outcome, type SummarizeResponse, summarize } from "./client";
import { PasteForm } from "./components/PasteForm";
import { PhiBanner } from "./components/PhiBanner";
import { Review } from "./components/Review";

type Failure = Exclude<Outcome, { kind: "result" }>;

type View =
  | { readonly kind: "compose"; readonly failure: Failure | null }
  | { readonly kind: "sending" }
  | { readonly kind: "review"; readonly sent: string; readonly body: SummarizeResponse };

/** Anything but a result, said in place of one (L92, L100). */
function failureText(failure: Failure): string {
  if (failure.kind === "no-response") {
    return "No response from the server.";
  }
  const parts = [`HTTP ${String(failure.status)}`];
  if (failure.code !== null && failure.requestId !== null) {
    parts.push(failure.code, `request ${failure.requestId}`);
  }
  return `The request failed: ${parts.join(" · ")}`;
}

/** Compose, then review (L362): the paste box, or the note beside the text it came from. */
export function App() {
  const [draft, setDraft] = useState("");
  const [view, setView] = useState<View>({ kind: "compose", failure: null });

  async function send() {
    const sent = draft;
    setView({ kind: "sending" });
    const outcome = await summarize(sent);
    setView(
      outcome.kind === "result"
        ? { kind: "review", sent, body: outcome.body }
        : { kind: "compose", failure: outcome },
    );
  }

  return (
    <main>
      <header>
        <h1>NotePilot</h1>
        {view.kind === "review" && (
          <button
            type="button"
            onClick={() => {
              setView({ kind: "compose", failure: null });
            }}
          >
            New paste
          </button>
        )}
      </header>
      <PhiBanner />
      {view.kind === "review" ? (
        <Review sent={view.sent} body={view.body} />
      ) : (
        <>
          <PasteForm
            draft={draft}
            sending={view.kind === "sending"}
            onDraft={setDraft}
            onSubmit={() => {
              void send();
            }}
          />
          {view.kind === "compose" && view.failure !== null && (
            <p className="failure" role="alert">
              {failureText(view.failure)}
            </p>
          )}
        </>
      )}
    </main>
  );
}
