import type { SummarizeResponse } from "../client";

/** What produced the note (§12). The note id is plain text, not a link (L58). */
export function Receipt({ body }: { readonly body: SummarizeResponse }) {
  const { metadata, report, note_id: noteId } = body;
  const { input_tokens: input, output_tokens: output } = metadata.usage;
  return (
    <p className="receipt">
      {metadata.model} · prompt {metadata.prompt_version} · checks {report.checks_version} ·{" "}
      {String(input)} in / {String(output)} out · note {noteId}
    </p>
  );
}
