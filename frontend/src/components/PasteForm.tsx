import type { FormEvent } from "react";

interface Props {
  readonly draft: string;
  readonly sending: boolean;
  readonly onDraft: (draft: string) => void;
  readonly onSubmit: () => void;
}

/** The paste box and its button. While a request is in flight both are held (L362). */
export function PasteForm({ draft, sending, onDraft, onSubmit }: Props) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }
  return (
    <form className="paste" onSubmit={submit}>
      <label htmlFor="paste">Paste a note to summarize</label>
      <textarea
        id="paste"
        value={draft}
        readOnly={sending}
        rows={14}
        onChange={(event) => {
          onDraft(event.target.value);
        }}
      />
      <button type="submit" disabled={sending}>
        {sending ? "Summarizing…" : "Summarize"}
      </button>
    </form>
  );
}
