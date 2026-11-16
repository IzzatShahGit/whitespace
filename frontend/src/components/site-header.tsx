import { Logo } from "@/components/brand/logo";
import { ButtonLink } from "@/components/ui/button";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-line/60 bg-canvas/80 backdrop-blur-md">
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Logo />
        <div className="flex items-center gap-1 sm:gap-3">
          <a
            href="#how-it-works"
            className="hidden px-3 text-sm text-muted transition-colors hover:text-fg sm:block"
          >
            How it works
          </a>
          <ButtonLink href="/login" variant="ghost">
            Sign in
          </ButtonLink>
          <ButtonLink href="/signup" className="h-9 px-4">
            Get started
          </ButtonLink>
        </div>
      </nav>
    </header>
  );
}
