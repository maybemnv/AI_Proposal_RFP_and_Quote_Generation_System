import type {ValidationFlag} from "@/lib/api";

export function FlagList({flags}: {flags: ValidationFlag[]}) {
  if (!flags.length) return null;
  return <ul className="flag-list" aria-label="Validation flags">
    {flags.map((flag, index) => <li className={`flag-${flag.severity}`} key={`${flag.code}-${index}`}>
      <span className="flag-icon" aria-hidden="true">{flag.severity === "blocking" ? "!" : "i"}</span>
      <span><strong>{flag.code}</strong> {flag.message}</span>
    </li>)}
  </ul>;
}
