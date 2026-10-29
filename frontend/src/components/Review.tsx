import { useMemo, useState } from "react";

import type { SummarizeResponse } from "../client";
import { isEmpty, place, verdict } from "../findings";
import { codePoints } from "../slicing";
import { NoteView } from "./NoteView";
import { Receipt } from "./Receipt";
import { SafetyBanner } from "./SafetyBanner";
import { SourcePane } from "./SourcePane";
import { VerdictLine } from "./VerdictLine";

interface Props {
  /** The text that was sent, which the spans index (§9.10). */
  readonly sent: string;
  readonly body: SummarizeResponse;
}

/**
 * The review: the source as sent beside the note. A claim is active while hovered or in
 * focus, and a click pins it until clicked again (L362); the hovered claim wins, then the
 * focused one, then the pinned one.
 */
export function Review({ sent, body }: Props) {
  const { note, report } = body;
  const points = useMemo(() => codePoints(sent), [sent]);
  const placement = useMemo(() => place(note.claims, report), [note.claims, report]);
  const [hovered, setHovered] = useState<number | null>(null);
  const [focused, setFocused] = useState<number | null>(null);
  const [pinned, setPinned] = useState<number | null>(null);
  const active = hovered ?? focused ?? pinned;
  const claim = note.claims.find((candidate) => candidate.id === active) ?? null;
  if (isEmpty(note.claims, report)) {
    return (
      <div className="review">
        <SourcePane points={points} span={null} paraphrased={false} />
        <section className="note" aria-label="Note">
          <p>No clinical content recognized in this paste.</p>
          <Receipt body={body} />
        </section>
      </div>
    );
  }
  return (
    <div className="review">
      <SourcePane
        points={points}
        span={claim?.source_span ?? null}
        paraphrased={claim?.flags.includes("paraphrased") ?? false}
      />
      <section className="note" aria-label="Note">
        <p className="draft">DRAFT — unverified</p>
        <SafetyBanner noteLevel={placement.noteLevel} errored={placement.errored} />
        <VerdictLine verdict={verdict(report)} />
        <NoteView
          claims={note.claims}
          placement={placement}
          active={active}
          pinned={pinned}
          onHover={setHovered}
          onFocus={setFocused}
          onPin={(id) => {
            setPinned((current) => (current === id ? null : id));
          }}
        />
        <p className="passed">
          Passed ({placement.passed.length})
          {placement.passed.length > 0 &&
            `: ${placement.passed.map((result) => result.check).join(", ")}`}
        </p>
        <Receipt body={body} />
      </section>
    </div>
  );
}
