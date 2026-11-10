/**
 * Empty-state illustrations (A-10-T12): simple original line drawings in the brand palette,
 * decorative (`aria-hidden`). 96 × 96, black strokes with a yellow accent.
 */
export type IllustrationName = "documents" | "contacts" | "organisations" | "search" | "inbox";

const STROKE = "var(--n9-color-neutral-900)";
const ACCENT = "var(--n9-color-brand-yellow)";
const PAPER = "var(--n9-color-neutral-0)";

export function Illustration({ name }: { name: IllustrationName }) {
  return (
    <svg
      width="96"
      height="96"
      viewBox="0 0 96 96"
      fill="none"
      aria-hidden="true"
      focusable="false"
      data-illustration={name}
    >
      <circle cx="48" cy="48" r="44" fill="var(--n9-color-yellow-50)" />
      {name === "documents" ? (
        <>
          <rect
            x="30"
            y="22"
            width="36"
            height="48"
            rx="4"
            fill={PAPER}
            stroke={STROKE}
            strokeWidth="2.5"
          />
          <path
            d="M37 34h22M37 42h22M37 50h14"
            stroke={STROKE}
            strokeWidth="2.5"
            strokeLinecap="round"
          />
          <circle cx="62" cy="64" r="10" fill={ACCENT} stroke={STROKE} strokeWidth="2.5" />
          <path d="M62 59v10M57 64h10" stroke={STROKE} strokeWidth="2.5" strokeLinecap="round" />
        </>
      ) : name === "contacts" ? (
        <>
          <circle cx="40" cy="38" r="9" fill={PAPER} stroke={STROKE} strokeWidth="2.5" />
          <path
            d="M24 66c2-10 9-15 16-15s14 5 16 15"
            stroke={STROKE}
            strokeWidth="2.5"
            strokeLinecap="round"
            fill={PAPER}
          />
          <circle cx="62" cy="42" r="7" fill={ACCENT} stroke={STROKE} strokeWidth="2.5" />
          <path
            d="M52 64c1.5-7 6-11 10-11s9 4 11 11"
            stroke={STROKE}
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        </>
      ) : name === "organisations" ? (
        <>
          <rect
            x="26"
            y="34"
            width="20"
            height="34"
            rx="2"
            fill={PAPER}
            stroke={STROKE}
            strokeWidth="2.5"
          />
          <rect
            x="46"
            y="24"
            width="24"
            height="44"
            rx="2"
            fill={ACCENT}
            stroke={STROKE}
            strokeWidth="2.5"
          />
          <path
            d="M32 42h8M32 50h8M32 58h8M52 32h12M52 40h12M52 48h12M52 56h12"
            stroke={STROKE}
            strokeWidth="2.5"
            strokeLinecap="round"
          />
          <path d="M20 68h56" stroke={STROKE} strokeWidth="2.5" strokeLinecap="round" />
        </>
      ) : name === "search" ? (
        <>
          <circle cx="44" cy="44" r="16" fill={PAPER} stroke={STROKE} strokeWidth="2.5" />
          <path d="M56 56l12 12" stroke={STROKE} strokeWidth="4" strokeLinecap="round" />
          <path d="M38 44h12" stroke={ACCENT} strokeWidth="4" strokeLinecap="round" />
        </>
      ) : (
        <>
          <path
            d="M22 52l8-24h36l8 24v16H22z"
            fill={PAPER}
            stroke={STROKE}
            strokeWidth="2.5"
            strokeLinejoin="round"
          />
          <path
            d="M22 52h16l4 6h12l4-6h16"
            stroke={STROKE}
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill={ACCENT}
          />
        </>
      )}
    </svg>
  );
}
