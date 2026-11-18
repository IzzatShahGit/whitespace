import type { Metadata } from "next";
import { Suspense } from "react";

import { Unsubscribe } from "@/components/auth/email-links";

export const metadata: Metadata = { title: "Unsubscribe · Whitespace", referrer: "no-referrer" };

export default function UnsubscribePage() {
  return (
    <Suspense>
      <Unsubscribe />
    </Suspense>
  );
}
