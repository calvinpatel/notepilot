import { useId } from "react";

import type { components } from "../api";
import type { Placement } from "../findings";
import { ClaimCard } from "./ClaimCard";

type Claim = components["schemas"]["ClinicalClaim"];
type Section = Claim["section"];

const SECTIONS: readonly (readonly [Section, string])[] = [
  ["S", "Subjective"],
  ["O", "Objective"],
  ["A", "Assessment"],
  ["P", "Plan"],
];

interface Props {
  readonly claims: readonly Claim[];
  readonly placement: Placement;
  readonly active: number | null;
  readonly pinned: number | null;
  readonly onHover: (id: number | null) => void;
  readonly onFocus: (id: number | null) => void;
  readonly onPin: (id: number) => void;
}

/** The note's four sections, each always shown (D7). */
export function NoteView({ claims, placement, active, pinned, onHover, onFocus, onPin }: Props) {
  const prefix = useId();
  return (
    <>
      {SECTIONS.map(([section, heading]) => {
        const inSection = claims.filter((claim) => claim.section === section);
        return (
          <section key={section} aria-labelledby={`${prefix}-${section}`}>
            <h2 id={`${prefix}-${section}`}>{heading}</h2>
            {inSection.length === 0 ? (
              <p className="none">{section === "A" ? "No assessment documented" : "none stated"}</p>
            ) : (
              <ul className="claims">
                {inSection.map((claim) => (
                  <ClaimCard
                    key={claim.id}
                    claim={claim}
                    findings={placement.byClaim.get(claim.id) ?? []}
                    active={claim.id === active}
                    pinned={claim.id === pinned}
                    onHover={onHover}
                    onFocus={onFocus}
                    onPin={onPin}
                  />
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </>
  );
}
