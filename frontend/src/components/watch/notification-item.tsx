import { AlarmClock, Gavel, TrendingDown, TrendingUp, Users } from "lucide-react";
import Link from "next/link";

import { toneClass } from "@/components/ui/badge";
import type { Notification } from "@/lib/api/watch";
import { timeAgo } from "@/lib/time";

const ICONS = {
  imports_up: TrendingUp,
  imports_down: TrendingDown,
  share_up: TrendingUp,
  share_down: TrendingDown,
  rival_slipping: Users,
  follow_up: AlarmClock,
  tender: Gavel,
} as const;

function tone(n: Notification): "positive" | "negative" | "neutral" {
  const value = n.data["tone"];
  return value === "positive" || value === "negative" ? value : "neutral";
}

/** One alert: icon by kind, colour by meaning, the sentence with figures, and when. */
export function NotificationItem({
  notification: n,
  onOpen,
}: {
  notification: Notification;
  onOpen?: () => void;
}) {
  const Icon = ICONS[n.kind];
  const body = (
    <>
      <span
        className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ${toneClass[tone(n)]}`}
      >
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-start justify-between gap-2">
          <span className={`text-sm ${n.read_at ? "text-muted" : "font-medium text-fg"}`}>
            {n.title}
          </span>
          {!n.read_at && (
            <span aria-label="Unread" className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent" />
          )}
        </span>
        <span className="mt-0.5 block text-xs leading-5 text-muted">{n.body}</span>
        <span className="mt-1 block text-xs text-subtle">{timeAgo(n.created_at)}</span>
      </span>
    </>
  );
  const className = "flex gap-3 rounded-xl p-3 text-left transition-colors hover:bg-surface-2";
  return n.link ? (
    <Link href={n.link} onClick={onOpen} className={className}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}
