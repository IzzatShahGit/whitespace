import type { Metadata } from "next";

import { Glossary } from "@/components/views/glossary";

export const metadata: Metadata = { title: "Trade terms, simply · Whitespace" };

export default function LearnPage() {
  return <Glossary />;
}
