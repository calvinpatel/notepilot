import { useEffect, useId, useRef } from "react";

import { segments } from "../slicing";

interface Props {
  /** The sent text's code points (L177). */
  readonly points: readonly string[];
  /** The active claim's span, or null when no claim is active or it has none. */
  readonly span: readonly [number, number] | null;
  /** Yellow for a paraphrased claim (§9.7). */
  readonly paraphrased: boolean;
}

/** The text as sent, with the active claim's span marked: one highlight at a time (§9.10). */
export function SourcePane({ points, span, paraphrased }: Props) {
  const heading = useId();
  const mark = useRef<HTMLElement>(null);
  const cut = span === null ? null : segments(points, span);
  useEffect(() => {
    // jsdom has no scrollIntoView, hence the optional call
    mark.current?.scrollIntoView?.({ block: "nearest" });
  }, [span]);
  return (
    <section className="source" aria-labelledby={heading}>
      <h2 id={heading}>Source (as sent)</h2>
      <pre>
        {cut === null ? (
          points.join("")
        ) : (
          <>
            {cut.before}
            <mark ref={mark} className={paraphrased ? "paraphrased" : "grounded"}>
              {cut.marked}
            </mark>
            {cut.after}
          </>
        )}
      </pre>
    </section>
  );
}
