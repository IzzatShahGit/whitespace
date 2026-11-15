import { SignedInShell } from "@/components/app/signed-in-shell";

export default function SignedInLayout({ children }: LayoutProps<"/">) {
  return <SignedInShell>{children}</SignedInShell>;
}
