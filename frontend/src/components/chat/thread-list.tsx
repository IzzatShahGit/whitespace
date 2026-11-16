"use client";

import { MessageSquare, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { scriptProps } from "@/components/chat/script";
import { Skeleton } from "@/components/ui/empty";
import { type ChatThread, useChatThreads, useDeleteThread } from "@/lib/api/queries";

const DAY = 24 * 60 * 60 * 1000;

function group(threads: ChatThread[], now = new Date()): [string, ChatThread[]][] {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const label = (t: ChatThread) => {
    const at = new Date(t.updated_at).getTime();
    if (at >= today) return "Today";
    if (at >= today - DAY) return "Yesterday";
    if (at >= today - 7 * DAY) return "Previous 7 days";
    return "Older";
  };
  const groups = new Map<string, ChatThread[]>();
  for (const t of threads) groups.set(label(t), [...(groups.get(label(t)) ?? []), t]);
  return [...groups];
}

/** Past conversations, newest first, grouped by day; also used inside the phone sheet. */
export function ThreadList({
  current,
  onNew,
  onNavigate,
}: {
  current?: string;
  onNew: () => void;
  onNavigate?: () => void;
}) {
  const threads = useChatThreads();
  const remove = useDeleteThread();
  const router = useRouter();

  return (
    <nav aria-label="Conversations" className="flex flex-col gap-4">
      <button
        type="button"
        onClick={() => {
          onNew();
          onNavigate?.();
        }}
        className="flex h-11 items-center gap-2 rounded-xl border border-line bg-surface px-3 text-sm font-medium text-fg shadow-card transition-colors hover:border-line-strong hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-brand"
      >
        <Plus aria-hidden className="h-4 w-4 text-brand" />
        New conversation
      </button>

      {threads.isPending && (
        <div className="flex flex-col gap-2">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-9" />
          ))}
        </div>
      )}
      {threads.isError && (
        <p className="px-3 text-sm text-muted">Couldn’t load your conversations.</p>
      )}
      {threads.data?.length === 0 && (
        <p className="flex items-center gap-2 px-3 text-sm text-muted">
          <MessageSquare aria-hidden className="h-4 w-4 text-subtle" />
          Your conversations will show here.
        </p>
      )}

      {group(threads.data ?? []).map(([label, items]) => (
        <div key={label}>
          <h3 className="px-3 pb-1 text-xs font-medium text-subtle">{label}</h3>
          <ul className="flex flex-col gap-0.5">
            {items.map((t) => {
              const active = t.id === current;
              return (
                <li key={t.id} className="group relative">
                  <Link
                    href={`/app/ask?t=${t.id}`}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    {...scriptProps(
                      t.title,
                      `block truncate rounded-xl py-2 pr-11 pl-3 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-brand ${
                        active
                          ? "bg-surface font-medium text-fg shadow-card"
                          : "text-muted hover:bg-surface-2 hover:text-fg"
                      }`,
                      "leading-6",
                    )}
                  >
                    {t.title}
                  </Link>
                  <button
                    type="button"
                    aria-label={`Delete “${t.title}”`}
                    disabled={remove.isPending && remove.variables === t.id}
                    onClick={() =>
                      remove.mutate(t.id, {
                        onSuccess: () => t.id === current && router.replace("/app/ask"),
                      })
                    }
                    className="absolute top-1/2 right-1 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-subtle transition-all hover:bg-negative-soft hover:text-negative focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-brand pointer-fine:opacity-0 pointer-fine:group-hover:opacity-100"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
