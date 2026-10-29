import { useEffect, useState } from "react";

import { type Outcome, type SummarizeResponse, summarize } from "./client";
import { failureCopy } from "./copy";
import { PasteForm } from "./components/PasteForm";
import { PhiBanner } from "./components/PhiBanner";
import { Review } from "./components/Review";

type Failure = Exclude<Outcome, { kind: "result" }>;

type View =
  | { readonly kind: "compose"; readonly failure: Failure | null }
  | { readonly kind: "sending" }
  | { readonly kind: "review"; readonly sent: string; readonly body: SummarizeResponse };

/** Compose, then review (L362): the paste box, or the note beside the text it came from. */
export function App() {
  const [draft, setDraft] = useState("");
  const [view, setView] = useState<View>({ kind: "compose", failure: null });
  const [elapsed, setElapsed] = useState(0);
  const sending = view.kind === "sending";

  // the button counts the seconds a request has been in flight (L363)
  useEffect(() => {
    if (!sending) {
      return undefined;
    }
    const timer = setInterval(() => {
      setElapsed((seconds) => seconds + 1);
    }, 1000);
    return () => {
      clearInterval(timer);
    };
  }, [sending]);

  async function send() {
    const sent = draft;
    setElapsed(0);
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
            sending={sending}
            elapsed={elapsed}
            onDraft={setDraft}
            onSubmit={() => {
              void send();
            }}
          />
          {view.kind === "compose" && view.failure !== null && (
            <p className="failure" role="alert">
              {failureCopy(view.failure)}
            </p>
          )}
        </>
      )}
    </main>
  );
}
