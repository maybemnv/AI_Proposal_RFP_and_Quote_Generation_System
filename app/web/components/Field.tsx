import type {InputHTMLAttributes, ReactNode} from "react";

type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: ReactNode;
};

export function Field({label, hint, id, ...props}: FieldProps) {
  return <label className="field" htmlFor={id}>
    <span className="field-label">{label}</span>
    <input id={id} {...props} />
    {hint && <span className="field-hint">{hint}</span>}
  </label>;
}
