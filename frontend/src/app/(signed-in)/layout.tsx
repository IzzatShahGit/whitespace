import { SignedInShell } from "@/components/app/signed-in-shell";

// Every page under here renders only after the browser confirms the session
// (SessionGate), so Next's instant-navigation check can't prerender it. Each page opts
// out with `export const instant = false`: Next reads that per page, not from layouts.

export default function SignedInLayout({ children }: LayoutProps<"/">) {
  return <SignedInShell>{children}</SignedInShell>;
}
