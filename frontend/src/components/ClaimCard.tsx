import type { components } from "../api";
import { Finding } from "./Finding";

type Claim = components["schemas"]["ClinicalClaim"];
type Result = components["schemas"]["EvalResult"];

interface Props {
  readonly claim: Claim;
  readonly findings: readonly Result[];
  readonly active: boolean;
  readonly pinned: boolean;
  readonly onHover: (id: number | null) => void;
  readonly onFocus: (id: number | null) => void;
  readonly onPin: (id: number) => void;
}

/** A claim, its flags as text, its quote, and the fired results naming it (§9.7, §9.10). */
export function ClaimCard({ claim, findings, active, pinned, onHover, onFocus, onPin }: Props) {
  return (
    <li
      className={active ? "claim active" : "claim"}
      onMouseEnter={() => {
        onHover(claim.id);
      }}
      onMouseLeave={() => {
        onHover(null);
      }}
    >
      <button
        type="button"
        aria-pressed={pinned}
        onFocus={() => {
          onFocus(claim.id);
        }}
        onBlur={() => {
          onFocus(null);
        }}
        onClick={() => {
          onPin(claim.id);
        }}
      >
        <span className="claim-id">#{claim.id}</span> {claim.text}
      </button>
      {claim.flags.map((flag) => (
        <span key={flag} className={`flag ${flag}`}>
          {flag.toUpperCase()}
        </span>
      ))}
      <q>{claim.source_quote}</q>
      {findings.length > 0 && (
        <ul>
          {findings.map((result, index) => (
            <Finding key={`${result.check}-${String(index)}`} result={result} />
          ))}
        </ul>
      )}
    </li>
  );
}
