// Sending a question to the guide: the reply streams back as server-sent events.
// (EventSource can't POST, so this reads the stream from fetch.)

import { refreshSession } from "@/lib/api/client";
import { ApiError, type ChatEvent } from "@/lib/api/queries";

const URL = "/api/v1/chat/messages";

function post(body: { thread_id: string | null; text: string }, signal?: AbortSignal) {
  return fetch(URL, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json", accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
}

async function failure(response: Response): Promise<ApiError> {
  const detail = await response
    .json()
    .then((b: { detail?: unknown }) => (typeof b.detail === "string" ? b.detail : undefined))
    .catch(() => undefined);
  return new ApiError(response.status, detail ?? "Couldn't reach the guide. Please try again.");
}

/** Ask a question; `onEvent` gets each event as it arrives. Resolves when the stream ends. */
export async function streamChat(
  body: { thread_id: string | null; text: string },
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response = await post(body, signal);
  if (response.status === 401 && (await refreshSession())) response = await post(body, signal);
  if (!response.ok || !response.body) throw await failure(response);

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += value;
    let end: number;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)) as ChatEvent);
      }
    }
  }
}
