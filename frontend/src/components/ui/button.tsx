import Link from "next/link";
import type { ComponentProps } from "react";

type Variant = "primary" | "secondary" | "ghost";

const base =
  "inline-flex items-center justify-center gap-2 rounded-full px-5 h-11 text-sm font-medium " +
  "transition-all duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 " +
  "focus-visible:outline-ember disabled:opacity-50 disabled:pointer-events-none";

const variants: Record<Variant, string> = {
  primary:
    "bg-ember text-ink hover:bg-[#ec8a5c] hover:-translate-y-0.5 hover:shadow-[0_8px_24px_-8px_var(--ember)]",
  secondary: "border border-ink-line text-cream hover:border-sage-dim hover:bg-ink-raised",
  ghost: "text-sage hover:text-cream",
};

export function buttonClass(variant: Variant = "primary", className = "") {
  return `${base} ${variants[variant]} ${className}`;
}

export function Button({
  variant = "primary",
  className,
  ...props
}: ComponentProps<"button"> & { variant?: Variant }) {
  return <button className={buttonClass(variant, className)} {...props} />;
}

export function ButtonLink({
  variant = "primary",
  className,
  ...props
}: ComponentProps<typeof Link> & { variant?: Variant }) {
  return <Link className={buttonClass(variant, className)} {...props} />;
}
