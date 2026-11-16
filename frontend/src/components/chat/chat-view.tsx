"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowUp,
  Calculator,
  CircleAlert,
  CircleCheck,
  CornerDownRight,
  History,
  LoaderCircle,
  Newspaper,
  PackageSearch,
  Plus,
  Scale,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  TriangleAlert,
  X,
} from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type KeyboardEvent, type RefObject, useEffect, useRef, useState } from "react";

import { IsoGrid } from "@/components/brand/iso-grid";
import { ChatCardView } from "@/components/chat/cards";
import { Markdown } from "@/components/chat/markdown";
import { scriptProps } from "@/components/chat/script";
import { ThreadList } from "@/components/chat/thread-list";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/empty";
import { streamChat } from "@/lib/api/chat-stream";
import {
  ApiError,
  type ChatCard,
  type ChatMessage,
  keys,
  useChatSuggestions,
  useChatThread,
  useMe,
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

function Avatar({ large = false }: { large?: boolean }) {
  return (
    <span
      aria-hidden
      className={`flex shrink-0 items-center justify-center rounded-full border border-line bg-surface shadow-card ${
        large ? "h-14 w-14" : "h-8 w-8"
      }`}
    >
      <IsoGrid className={large ? "w-9" : "w-5"} />
    </span>
  );
}

function Step({ text, done }: { text: string; done: boolean }) {
  return (
    <li className="flex items-center gap-2 text-sm text-muted">
      {done ? (
        <CircleCheck aria-hidden className="h-4 w-4 text-positive" />
      ) : (
        <LoaderCircle
          aria-hidden
          className="h-4 w-4 animate-spin text-brand motion-reduce:animate-none"
        />
      )}
      <span className={done ? "" : "text-fg"}>{text}</span>
      <span className="sr-only">{done ? "(done)" : "(working)"}</span>
    </li>
  );
}

function Grounded({ value }: { value: boolean | null | undefined }) {
  if (value === null || value === undefined) return null;
  return value ? (
    <div>
      <Badge tone="positive" icon={<ShieldCheck />}>
        Every figure checked against the data
      </Badge>
    </div>
  ) : (
    <p className="flex items-start gap-1.5 rounded-xl bg-caution-soft px-3 py-2 text-xs leading-5 text-caution">
      <TriangleAlert aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      Some figures couldn’t be matched to the data. Check them on the cards.
    </p>
  );
}

function FollowUps({
  items,
  onPick,
  disabled,
}: {
  items: string[];
  onPick: (text: string) => void;
  disabled: boolean;
}) {
  if (!items.length) return null;
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs font-medium text-subtle">Ask next</p>
      <div className="flex flex-wrap gap-2">
        {items.map((text) => (
          <button
            key={text}
            type="button"
            disabled={disabled}
            onClick={() => onPick(text)}
            {...scriptProps(
              text,
              "inline-flex min-h-9 items-center gap-1.5 rounded-full border border-line bg-surface px-3.5 py-1.5 text-left text-sm text-fg shadow-card transition-colors hover:border-brand/50 hover:bg-brand-soft focus-visible:outline-2 focus-visible:outline-brand disabled:opacity-50",
              "leading-5",
            )}
          >
            <CornerDownRight aria-hidden className="h-3.5 w-3.5 shrink-0 text-brand" />
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

function Question({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p
        {...scriptProps(
          text,
          "max-w-[85%] rounded-2xl rounded-br-md bg-brand-soft px-4 py-2.5 text-[15px] whitespace-pre-wrap text-fg",
          "leading-7",
        )}
      >
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
  onRetry,
  live = false,
  busy,
}: {
  content?: string;
  cards: ChatCard[];
  followUps: string[];
  grounded?: boolean | null;
  failed?: boolean;
  steps?: string[];
  onPick: (text: string) => void;
  onRetry?: () => void;
  live?: boolean;
  busy: boolean;
}) {
  return (
    <div className="flex gap-3">
      <Avatar />
      <div className="flex min-w-0 flex-1 flex-col gap-3 pt-1">
        <p className="text-sm font-medium">Whitespace</p>
        {steps && steps.length > 0 && (
          <ul className="flex flex-col gap-1.5" aria-label="Progress">
            {steps.map((step, i) => (
              <Step
                key={`${step}-${i}`}
                text={step}
                done={!live || i < steps.length - 1 || content !== undefined}
              />
            ))}
          </ul>
        )}
        {live && !content && !failed && (!steps || steps.length === 0) && (
          <ul aria-label="Progress">
            <Step text="Reading your question" done={false} />
          </ul>
        )}
        {content !== undefined &&
          (failed ? (
            <div className="flex flex-col items-start gap-2 rounded-xl bg-negative-soft px-4 py-3 text-sm text-negative">
              <p className="flex items-start gap-2">
                <CircleAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
                {content}
              </p>
              {onRetry && (
                <button
                  type="button"
                  onClick={onRetry}
                  disabled={busy}
                  className="rounded-lg px-2 py-1 font-medium underline underline-offset-4 hover:bg-negative/10"
                >
                  Try again
                </button>
              )}
            </div>
          ) : (
            <div className="rise-in">
              <Markdown text={content} />
            </div>
          ))}
        {cards.map((card, i) => (
          <ChatCardView key={`${card.type}-${i}`} card={card} />
        ))}
        {content !== undefined && !failed && <Grounded value={grounded} />}
        {content !== undefined && <FollowUps items={followUps} onPick={onPick} disabled={busy} />}
      </div>
    </div>
  );
}

function Message({
  message,
  onPick,
  busy,
}: {
  message: ChatMessage;
  onPick: (text: string) => void;
  busy: boolean;
}) {
  if (message.role === "user") return <Question text={message.content} />;
  if (message.status === "pending") {
    return (
      <Reply
        cards={[]}
        followUps={[]}
        steps={["Still working on this"]}
        onPick={onPick}
        busy={busy}
        live
      />
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
      busy={busy}
    />
  );
}

function Composer({
  disabled,
  onSend,
  initial = "",
  remaining,
}: {
  disabled: boolean;
  onSend: (text: string) => void;
  initial?: string;
  remaining?: number;
}) {
  // A question handed over from elsewhere (search, "Ask about this") is typed in, not sent:
  // the user stays in control of what spends their daily questions.
  const [text, setText] = useState(initial);
  const ref = useRef<HTMLTextAreaElement>(null);
  const tooLong = text.length > MAX_CHARS;
  const none = remaining === 0;

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
    <div>
      <div className="flex items-end gap-2 rounded-2xl border border-line-strong/60 bg-surface p-2 shadow-pop transition-colors focus-within:border-brand focus-within:ring-4 focus-within:ring-brand/10">
        <label htmlFor="ask" className="sr-only">
          Your question
        </label>
        <textarea
          id="ask"
          ref={ref}
          rows={1}
          value={text}
          maxLength={MAX_CHARS + 100}
          placeholder={none ? "No questions left today" : "Ask in any language…"}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          aria-describedby="ask-hint"
          {...scriptProps(
            text,
            "block max-h-[200px] min-h-11 w-full flex-1 resize-none bg-transparent px-3 py-2.5 text-base text-fg outline-none placeholder:text-subtle",
            "leading-6",
          )}
        />
        <button
          type="button"
          onClick={send}
          disabled={disabled || !text.trim() || tooLong}
          aria-label="Send"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-action text-white shadow-card transition-all hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand active:scale-95 disabled:opacity-40"
        >
          {disabled ? (
            <LoaderCircle className="h-5 w-5 animate-spin motion-reduce:animate-none" />
          ) : (
            <ArrowUp className="h-5 w-5" strokeWidth={2.2} />
          )}
        </button>
      </div>
      <p
        id="ask-hint"
        className="mt-2 flex flex-wrap justify-center gap-x-1.5 px-2 text-center text-xs text-subtle"
      >
        {text.length > MAX_CHARS - 200 ? (
          <span className={tooLong ? "font-medium text-negative" : ""}>
            {text.length.toLocaleString("en")}/{MAX_CHARS.toLocaleString("en")} characters
          </span>
        ) : (
          remaining !== undefined && (
            <span>
              {remaining} question{remaining === 1 ? "" : "s"} left today
            </span>
          )
        )}
        <span aria-hidden>·</span>
        <span>Guidance from trade data, not legal or financial advice.</span>
      </p>
    </div>
  );
}

/** Starter icons, picked from the words of each personalised suggestion. */
function suggestionIcon(text: string) {
  const t = text.toLowerCase();
  if (/news|latest/.test(t)) return Newspaper;
  if (/buy|supplier|source/.test(t)) return PackageSearch;
  if (/lakh|crore|worth|price|compete/.test(t)) return Calculator;
  if (/compare/.test(t)) return Scale;
  if (/sell|market/.test(t)) return TrendingUp;
  return Sparkles;
}

const LANGUAGES = ["English", "اردو", "Roman Urdu", "বাংলা", "Türkçe", "Tiếng Việt", "العربية"];

function Welcome({ onPick, busy }: { onPick: (text: string) => void; busy: boolean }) {
  const me = useMe();
  const suggestions = useChatSuggestions();
  const first = me.data?.full_name.split(" ")[0];
  return (
    <div className="rise-in flex flex-1 flex-col justify-center gap-8 py-8 sm:py-12">
      <div className="flex flex-col items-center text-center">
        <Avatar large />
        <h1 className="mt-5 text-2xl font-semibold tracking-tight text-balance sm:text-3xl">
          {first ? `What would you like to know, ${first}?` : "What would you like to know?"}
        </h1>
        <p className="mt-2 max-w-xl text-pretty text-muted">
          Ask where to sell, where to buy, or what your stock is worth abroad. Answers come from
          customs data, and every figure is checked before you see it.
        </p>
        <p className="mt-3 flex flex-wrap justify-center gap-x-2 gap-y-1 text-sm text-subtle">
          <span>Ask in</span>
          {LANGUAGES.map((l) => (
            <span key={l} {...scriptProps(l, "text-muted")}>
              {l}
            </span>
          ))}
        </p>
      </div>
      <div className="grid gap-2.5 sm:grid-cols-2">
        {suggestions.isPending &&
          [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[72px] rounded-2xl" />)}
        {suggestions.data?.prompts.map((p) => {
          const Icon = suggestionIcon(p);
          return (
            <button
              key={p}
              type="button"
              disabled={busy || suggestions.data.remaining_today === 0}
              onClick={() => onPick(p)}
              className="group flex items-start gap-3 rounded-2xl border border-line bg-surface p-4 text-left shadow-card transition-colors hover:border-brand/50 hover:bg-brand-soft/40 focus-visible:outline-2 focus-visible:outline-brand disabled:opacity-50"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-soft text-brand">
                <Icon aria-hidden className="h-4 w-4" />
              </span>
              <span {...scriptProps(p, "pt-1 text-sm text-fg", "leading-5")}>{p}</span>
            </button>
          );
        })}
      </div>
      {suggestions.data && (
        <p className="text-center text-sm text-muted">
          <span className="font-medium text-fg tabular-nums">
            {suggestions.data.remaining_today}
          </span>{" "}
          questions left today. Starters use one too.
        </p>
      )}
    </div>
  );
}

/** Phones and tablets: past conversations in a sheet from the left. */
function ConversationsSheet({
  dialog,
  current,
  onNew,
}: {
  dialog: RefObject<HTMLDialogElement | null>;
  current?: string;
  onNew: () => void;
}) {
  const close = () => dialog.current?.close();
  return (
    <dialog
      ref={dialog}
      aria-label="Conversations"
      onClick={(e) => e.target === dialog.current && close()}
      className="fixed inset-y-0 left-0 m-0 h-dvh max-h-dvh w-[min(22rem,88vw)] overflow-y-auto border-r border-line bg-canvas p-0 text-fg shadow-pop backdrop:bg-black/40 open:animate-[pop-in_200ms_ease-out] lg:hidden"
    >
      <div className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-line bg-canvas px-4">
        <h2 className="text-base font-semibold">Conversations</h2>
        <button
          type="button"
          onClick={close}
          aria-label="Close"
          className="flex h-11 w-11 items-center justify-center rounded-xl text-muted hover:bg-surface-2 hover:text-fg focus-visible:outline-2 focus-visible:outline-brand"
        >
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="p-3 pb-[calc(1rem+env(safe-area-inset-bottom))]">
        <ThreadList current={current} onNew={onNew} onNavigate={close} />
      </div>
    </dialog>
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
  const sheet = useRef<HTMLDialogElement>(null);

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
  const title = empty ? "New conversation" : (thread.data?.title ?? turn?.question ?? "");

  return (
    <div className="flex flex-1">
      <aside className="sticky top-16 hidden h-[calc(100dvh-4rem)] w-72 shrink-0 overflow-y-auto border-r border-line px-3 py-4 lg:block">
        <ThreadList current={threadId} onNew={startNew} />
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-14 items-center gap-2 border-b border-line/70 px-2 sm:px-4 lg:px-6">
          <button
            type="button"
            onClick={() => sheet.current?.showModal()}
            className="flex h-11 items-center gap-2 rounded-xl px-3 text-sm text-muted hover:bg-surface-2 hover:text-fg focus-visible:outline-2 focus-visible:outline-brand lg:hidden"
          >
            <History aria-hidden className="h-4 w-4" />
            <span className="sr-only sm:not-sr-only">History</span>
          </button>
          <h1
            {...scriptProps(
              title,
              "min-w-0 flex-1 truncate text-sm font-medium sm:text-base",
              "leading-6",
            )}
          >
            {title || "Conversation"}
          </h1>
          {!empty && (
            <button
              type="button"
              onClick={startNew}
              className="flex h-11 items-center gap-1.5 rounded-xl px-3 text-sm font-medium text-brand hover:bg-brand-soft focus-visible:outline-2 focus-visible:outline-brand"
            >
              <Plus aria-hidden className="h-4 w-4" />
              New
            </button>
          )}
        </div>

        <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 sm:px-6">
          {empty ? (
            <Welcome onPick={send} busy={streaming} />
          ) : (
            <div className="flex flex-1 flex-col gap-8 py-6 sm:py-8" aria-live="polite">
              {thread.isPending && threadId && !turn && (
                <div className="flex flex-col gap-6" aria-label="Loading conversation">
                  <Skeleton className="ml-auto h-12 w-2/3 rounded-2xl" />
                  <Skeleton className="h-40 w-full rounded-2xl" />
                </div>
              )}
              {thread.isError && !turn && (
                <div className="flex items-start gap-2 rounded-xl bg-surface-2 px-4 py-3 text-sm text-muted">
                  <CircleAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
                  This conversation couldn’t be loaded. It may have been deleted; start a new one
                  below.
                </div>
              )}
              {stored.map((m) => (
                <Message key={m.id} message={m} onPick={send} busy={streaming} />
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
                    onRetry={turn.messageId ? undefined : () => send(turn.question)}
                    live={streaming}
                    busy={streaming}
                  />
                </>
              )}
              <div ref={bottom} />
            </div>
          )}

          {/* Clears the phone tab bar (64px + safe area); flush to the bottom on desktop. */}
          <div className="sticky bottom-[calc(64px+env(safe-area-inset-bottom))] z-10 -mx-4 bg-gradient-to-t from-canvas from-70% to-transparent px-4 pt-6 pb-3 sm:-mx-6 sm:px-6 lg:bottom-0 lg:pb-5">
            <Composer
              disabled={streaming}
              onSend={send}
              initial={params.get("q") ?? ""}
              remaining={suggestions.data?.remaining_today}
            />
          </div>
        </div>
      </main>

      <ConversationsSheet dialog={sheet} current={threadId} onNew={startNew} />
    </div>
  );
}
