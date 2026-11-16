import { Logo } from "@/components/brand/logo";
import { ButtonLink } from "@/components/ui/button";

const LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#inside", label: "What’s inside" },
  { href: "#data", label: "The data" },
];

/** Signed-out header: the brand, three anchors, and the two ways in. */
export function LandingHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-line/70 bg-canvas/85 backdrop-blur-xl">
      <nav
        aria-label="Main"
        className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6"
      >
        <Logo />
        <div className="hidden items-center gap-1 md:flex">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:bg-surface-2 hover:text-fg focus-visible:outline-2 focus-visible:outline-brand"
            >
              {link.label}
            </a>
          ))}
        </div>
        <div className="flex items-center gap-1 sm:gap-2">
          <ButtonLink href="/login" variant="ghost" className="px-3">
            Sign in
          </ButtonLink>
          <ButtonLink href="/signup" className="px-3 sm:px-4">
            Start free
          </ButtonLink>
        </div>
      </nav>
    </header>
  );
}
