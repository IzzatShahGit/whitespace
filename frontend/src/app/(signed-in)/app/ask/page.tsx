import type { Metadata } from "next";
import { Suspense } from "react";

import { ChatView } from "@/components/chat/chat-view";
import { Loading } from "@/components/views/states";

export const metadata: Metadata = { title: "Ask Whitespace" };

// The open conversation comes from the URL (?t=), read at request time.
export default function AskPage() {
  return (
    <Suspense fallback={<Loading />}>
      <ChatView />
    </Suspense>
  );
}
