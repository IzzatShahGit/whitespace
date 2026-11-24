import type { Metadata } from "next";

import { Glossary } from "@/components/views/glossary";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Trade terms, simply · Whitespace" };

export default function LearnPage() {
  return <Glossary />;
}
