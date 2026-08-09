import type {ButtonHTMLAttributes, ReactNode} from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  tone?: "primary" | "secondary" | "quiet" | "danger";
};

export function Button({children, tone = "primary", className = "", ...props}: ButtonProps) {
  return <button className={`button button-${tone} ${className}`} {...props}>{children}</button>;
}
