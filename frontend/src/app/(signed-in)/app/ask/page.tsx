import type { Metadata } from "next";
import { Suspense } from "react";

import { ChatView } from "@/components/chat/chat-view";
import { urduFont } from "@/components/chat/urdu-font";
import { Loading } from "@/components/views/states";

export const metadata: Metadata = { title: "Ask Whitespace" };

// The open conversation comes from the URL (?t=), read at request time.
export default function AskPage() {
  return (
    <div className={`${urduFont.variable} flex flex-1 flex-col`}>
      <Suspense fallback={<Loading />}>
        <ChatView />
      </Suspense>
    </div>
  );
}
