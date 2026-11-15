"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";

import { ChatCardView } from "@/components/chat/cards";
import { Markdown } from "@/components/chat/markdown";
import { streamChat } from "@/lib/api/chat-stream";
import {
  ApiError,
  type ChatCard,
  type ChatMessage,
  keys,
  useChatSuggestions,
  useChatThread,
  useChatThreads,
  useDeleteThread,
} from "@/lib/api/queries";

const MAX_CHARS = 1500;

/** The reply being written right now, shown live from the stream. */
type Turn = {
  threadId: string | null;
  messageId?: string;
  question: string;
  steps: string[];
  cards: ChatCard[];
  answer?: string;
  followUps: string[];
  grounded?: boolean | null;
  error?: string;
};

function Check({ done }: { done: boolean }) {
  return done ? (
    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 text-ember" fill="none" aria-hidden>
      <path
        d="M3 8.5 6.5 12 13 4.5"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  ) : (
    <span
      aria-hidden
      className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-sage-dim border-t-ember"
    />
  );
}

function Grounded({ value }: { value: boolean | null | undefined }) {
  if (value === null || value === undefined) return null;
  return value ? (
    <p className="flex items-center gap-1.5 text-xs text-sage-dim">
      <Check done /> Every figure checked against the data
    </p>
  ) : (
    <p className="text-xs text-caution">
      Some figures couldn’t be matched to the data. Check them on the cards.
    </p>
  );
}

function FollowUps({ items, onPick }: { items: string[]; onPick: (text: string) => void }) {
  if (!items.length) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((text) => (
        <button
          key={text}
          type="button"
          onClick={() => onPick(text)}
          className="rounded-full border border-ink-line px-3 py-1.5 text-xs text-sage transition-colors hover:border-ember/60 hover:text-cream"
        >
          {text}
        </button>
      ))}
    </div>
  );
}

function Question({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[85%] rounded-2xl rounded-br-md bg-ember/15 px-4 py-2.5 text-[15px] leading-7 whitespace-pre-wrap text-cream">
        {text}
      </p>
    </div>
  );
}

function Reply({
  content,
  cards,
  followUps,
  grounded,
  failed,
  steps,
  onPick,
  live = false,
}: {
  content?: string;
  cards: ChatCard[];
  followUps: string[];
  grounded?: boolean | null;
  failed?: boolean;
  steps?: string[];
  onPick: (text: string) => void;
  live?: boolean;
}) {
  return (
    <div className="flex flex-col gap-3">
      {steps && steps.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {steps.map((step, i) => (
            <li key={`${step}-${i}`} className="rise-in flex items-center gap-2 text-sm text-sage">
              <Check done={!live || i < steps.length - 1 || content !== undefined} />
              {step}
            </li>
          ))}
        </ul>
      )}
      {live && !content && !failed && (!steps || steps.length === 0) && (
        <p className="flex items-center gap-2 text-sm text-sage">
          <Check done={false} /> Thinking
        </p>
      )}
      {content !== undefined &&
        (failed ? (
          <p className="rounded-xl bg-caution-bg px-4 py-3 text-sm text-caution">{content}</p>
        ) : (
          <div className="rise-in">
            <Markdown text={content} />
          </div>
        ))}
      {cards.map((card, i) => (
        <ChatCardView key={`${card.type}-${i}`} card={card} />
      ))}
      {content !== undefined && !failed && <Grounded value={grounded} />}
      {content !== undefined && <FollowUps items={followUps} onPick={onPick} />}
    </div>
  );
}

function Message({ message, onPick }: { message: ChatMessage; onPick: (text: string) => void }) {
  if (message.role === "user") return <Question text={message.content} />;
  if (message.status === "pending") {
    return (
      <Reply cards={[]} followUps={[]} steps={["Still working on this"]} onPick={onPick} live />
    );
  }
  return (
    <Reply
      content={message.content}
      cards={message.cards}
      followUps={message.follow_ups}
      grounded={message.grounded}
      failed={message.status === "failed"}
      onPick={onPick}
    />
  );
}

function Composer({ disabled, onSend }: { disabled: boolean; onSend: (text: string) => void }) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  function send() {
    const value = text.trim();
    if (!value || disabled || value.length > MAX_CHARS) return;
    onSend(value);
    setText("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send();
    }
  }

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  return (
    <div className="rounded-2xl border border-ink-line bg-ink-raised p-2 transition-colors focus-within:border-ember/60">
      <label htmlFor="ask" className="sr-only">
        Ask Whitespace
      </label>
      <textarea
        id="ask"
        ref={ref}
        rows={1}
        value={text}
        maxLength={MAX_CHARS + 100}
        placeholder="Ask anything about selling or buying abroad, in any language"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        className="block max-h-[200px] w-full resize-none bg-transparent px-3 py-2 text-[15px] text-cream outline-none placeholder:text-sage-dim/70"
      />
      <div className="flex items-center justify-between gap-3 px-2 pb-1">
        <span className={`text-xs ${text.length > MAX_CHARS ? "text-caution" : "text-sage-dim"}`}>
          {text.length > MAX_CHARS - 200 ? `${text.length}/${MAX_CHARS}` : "Enter to send"}
        </span>
        <button
          type="button"
          onClick={send}
          disabled={disabled || !text.trim() || text.length > MAX_CHARS}
          aria-label="Send"
          className="flex h-9 w-9 items-center justify-center rounded-full bg-ember text-ink transition-all hover:bg-[#ec8a5c] disabled:opacity-40"
        >
          <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" aria-hidden>
            <path
              d="M8 13V3M3.5 7.5 8 3l4.5 4.5"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}

function ThreadList({ current, onNew }: { current?: string; onNew: () => void }) {
  const threads = useChatThreads();
  const remove = useDeleteThread();
  const router = useRouter();
  return (
    <nav aria-label="Conversations" className="flex flex-col gap-2">
      <button
        type="button"
        onClick={onNew}
        className="rounded-xl border border-ink-line px-3 py-2 text-left text-sm text-cream hover:border-ember/60"
      >
        + New conversation
      </button>
      <ul className="flex flex-col gap-0.5">
        {threads.data?.map((t) => (
          <li key={t.id} className="group relative">
            <Link
              href={`/app/ask?t=${t.id}`}
              aria-current={t.id === current ? "page" : undefined}
              className={`block truncate rounded-lg px-3 py-2 pr-8 text-sm ${
                t.id === current ? "bg-ink-raised text-cream" : "text-sage hover:text-cream"
              }`}
            >
              {t.title}
            </Link>
            <button
              type="button"
              aria-label={`Delete “${t.title}”`}
              onClick={() =>
                remove.mutate(t.id, {
                  onSuccess: () => t.id === current && router.replace("/app/ask"),
                })
              }
              className="absolute top-1/2 right-2 hidden -translate-y-1/2 rounded px-1 text-sage-dim group-hover:block hover:text-caution focus:block"
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Ask Whitespace: a guide that answers from the data, in the user's own language. */
export function ChatView() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const client = useQueryClient();
  const threadId = params.get("t") ?? undefined;
  const [turn, setTurn] = useState<Turn | null>(null);
  const streaming = turn !== null && turn.answer === undefined && turn.error === undefined;
  const thread = useChatThread(threadId, { paused: streaming });
  const suggestions = useChatSuggestions();
  const bottom = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => () => abort.current?.abort(), []); // leaving the page stops listening (the reply still saves)
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turn, thread.data?.messages.length]);

  async function send(text: string) {
    if (streaming) return;
    const controller = new AbortController();
    abort.current = controller;
    let current: Turn = {
      threadId: threadId ?? null,
      question: text,
      steps: [],
      cards: [],
      followUps: [],
    };
    const update = (patch: Partial<Turn>) => {
      current = { ...current, ...patch };
      setTurn(current);
    };
    update({});
    try {
      await streamChat(
        { thread_id: threadId ?? null, text },
        (event) => {
          if (event.event === "thread" && event.thread_id) {
            update({ threadId: event.thread_id, messageId: event.message_id ?? undefined });
            if (event.thread_id !== threadId) {
              router.replace(`${pathname}?t=${event.thread_id}`, { scroll: false });
            }
          } else if (event.event === "status" && event.text) {
            update({ steps: [...current.steps, event.text] });
          } else if (event.event === "card" && event.card) {
            update({ cards: [...current.cards, event.card] });
          } else if (event.event === "answer") {
            update({
              answer: event.text ?? "",
              followUps: event.follow_ups ?? [],
              grounded: event.grounded,
            });
          } else if (event.event === "error") {
            update({ error: event.text ?? "Something went wrong." });
          }
        },
        controller.signal,
      );
    } catch (e) {
      if (controller.signal.aborted) return;
      update({ error: e instanceof ApiError ? e.message : "Couldn’t reach the guide." });
      if (!current.messageId) return; // nothing was saved: keep the error in view
    }
    // The reply is saved: show the stored version (same content) and refresh the lists.
    void client.invalidateQueries({ queryKey: keys.chatThreads });
    void client.invalidateQueries({ queryKey: keys.chatSuggestions });
    if (current.threadId) {
      await client.refetchQueries({ queryKey: keys.chatThread(current.threadId) });
    }
    setTurn((t) => (t === current ? null : t));
  }

  function startNew() {
    abort.current?.abort();
    setTurn(null);
    router.replace(pathname);
  }

  // While a turn is live, hide its stored copies (the question and pending reply).
  const stored = (thread.data?.messages ?? []).filter((m, i, all) => {
    if (!turn?.messageId) return true;
    if (m.id === turn.messageId) return false;
    return !(all[i + 1]?.id === turn.messageId && m.role === "user");
  });
  const empty = !threadId && !turn;

  return (
    <main className="mx-auto grid w-full max-w-6xl flex-1 gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[15rem_1fr]">
      <aside className="hidden lg:block">
        <ThreadList current={threadId} onNew={startNew} />
      </aside>

      <section className="mx-auto flex w-full max-w-3xl min-w-0 flex-col">
        <div className="flex items-center justify-between gap-3 lg:hidden">
          <Link href="/app/ask" onClick={startNew} className="text-sm text-sage hover:text-cream">
            + New conversation
          </Link>
        </div>

        {empty ? (
          <div className="rise-in flex flex-1 flex-col justify-center gap-6 py-10">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Ask Whitespace</h1>
              <p className="mt-2 max-w-xl text-sage">
                Your trade guide. Ask where to sell, where to buy, or what your stock is worth
                abroad, in any language. Every figure comes from customs data, and you see it on the
                cards.
              </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {suggestions.data?.prompts.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => send(p)}
                  className="rounded-2xl border border-ink-line bg-ink-raised p-4 text-left text-sm text-sage transition-all hover:-translate-y-0.5 hover:border-ember/50 hover:text-cream"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-1 flex-col gap-8 py-6" aria-live="polite">
            {thread.isError && !turn && (
              <p className="text-sm text-sage">This conversation couldn’t be loaded.</p>
            )}
            {stored.map((m) => (
              <Message key={m.id} message={m} onPick={send} />
            ))}
            {turn && (
              <>
                <Question text={turn.question} />
                <Reply
                  content={turn.error ?? turn.answer}
                  failed={turn.error !== undefined}
                  cards={turn.cards}
                  followUps={turn.followUps}
                  grounded={turn.grounded}
                  steps={turn.steps}
                  onPick={send}
                  live={streaming}
                />
              </>
            )}
            <div ref={bottom} />
          </div>
        )}

        <div className="sticky bottom-0 bg-gradient-to-t from-ink via-ink to-transparent pt-4 pb-2">
          <Composer disabled={streaming} onSend={send} />
          <p className="mt-2 text-center text-[11px] text-sage-dim">
            {suggestions.data ? `${suggestions.data.remaining_today} questions left today · ` : ""}
            Guidance from trade data, not legal or financial advice.
          </p>
        </div>
      </section>
    </main>
  );
}
