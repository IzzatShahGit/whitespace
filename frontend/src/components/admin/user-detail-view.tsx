"use client";

import {
  ArrowLeft,
  Ban,
  CalendarDays,
  CircleCheck,
  Compass,
  FlaskConical,
  History,
  LogOut,
  MousePointerClick,
  Package,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { use } from "react";

import { AdminTabs, ago, dateTime, duration, n, Ranked, VisitRow } from "@/components/admin/parts";
import { SignInBadges } from "@/components/admin/users-view";
import { LoadError } from "@/components/markets/load-error";
import { Callout } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { Stat, StatGroup } from "@/components/ui/stat";
import {
  type AccountAction,
  type UserDetail,
  useAccountAction,
  useAdminUser,
} from "@/lib/api/admin";
import { isMissing } from "@/lib/api/queries";

const ACTION_LABEL: Record<string, string> = {
  disable: "Disabled",
  enable: "Enabled",
  sign_out: "Signed out everywhere",
  mark_test: "Marked as test",
  mark_real: "Marked as real",
};
const STAGE_LABEL: Record<string, string> = {
  to_contact: "To contact",
  emailed: "Emailed",
  replied: "Replied",
  samples: "Samples",
  negotiating: "Negotiating",
  won: "Won",
  lost: "Lost",
};

/** The last 90 days as a grid of squares: filled on days they used the app. */
function ActivityGrid({ days }: { days: string[] }) {
  const active = new Set(days);
  const today = new Date();
  const cells = Array.from({ length: 91 }, (_, i) => {
    const d = new Date(
      Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() - 90 + i),
    );
    return d.toISOString().slice(0, 10);
  });
  return (
    <div>
      <div
        role="img"
        aria-label={`Active on ${days.length} of the last 90 days`}
        className="grid grid-flow-col grid-rows-7 gap-1"
        style={{ gridTemplateColumns: "repeat(13, minmax(0, 1fr))" }}
      >
        {cells.map((day) => (
          <span
            key={day}
            title={day}
            className={`aspect-square rounded-[3px] ${active.has(day) ? "bg-brand" : "bg-surface-2"}`}
          />
        ))}
      </div>
      <p className="mt-2 text-xs text-muted">
        Active on {days.length} of the last 90 days (each square is a day, oldest first).
      </p>
    </div>
  );
}

function Facts({ rows }: { rows: [string, React.ReactNode][] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
      {rows.map(([label, value]) => (
        <div key={label} className="min-w-0">
          <dt className="text-xs text-subtle">{label}</dt>
          <dd className="mt-0.5 min-w-0 break-words text-fg">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Actions({ detail }: { detail: UserDetail }) {
  const u = detail.user;
  const action = useAccountAction(u.id);
  const run = (a: AccountAction, confirmText?: string) => {
    if (confirmText && !window.confirm(confirmText)) return;
    action.mutate(a);
  };
  return (
    <div className="flex flex-col items-start gap-2 sm:items-end">
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          disabled={action.isPending}
          onClick={() => run({ kind: "update", is_test: !u.is_test })}
        >
          <FlaskConical /> {u.is_test ? "Mark as real" : "Mark as test"}
        </Button>
        <Button
          variant="secondary"
          disabled={action.isPending || detail.open_sessions === 0}
          onClick={() => run({ kind: "sign_out" }, `Sign ${u.full_name} out on every device?`)}
        >
          <LogOut /> Sign out everywhere
        </Button>
        {!u.is_admin &&
          (u.is_active ? (
            <Button
              variant="secondary"
              disabled={action.isPending}
              className="text-negative"
              onClick={() =>
                run(
                  { kind: "update", is_active: false },
                  `Disable ${u.full_name}'s account? They are signed out at once and can't sign in until you enable it again. Their data is kept.`,
                )
              }
            >
              <Ban /> Disable
            </Button>
          ) : (
            <Button
              variant="secondary"
              disabled={action.isPending}
              onClick={() => run({ kind: "update", is_active: true })}
            >
              <CircleCheck /> Enable
            </Button>
          ))}
      </div>
      {action.isError && <p className="text-sm text-negative">{action.error.message}</p>}
    </div>
  );
}

export function UserDetailView({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const detail = useAdminUser(id);

  if (detail.isPending) {
    return (
      <Page>
        <Skeleton className="h-20" />
        <Skeleton className="h-24" />
        <Skeleton className="h-80" />
      </Page>
    );
  }
  if (!detail.data) {
    return (
      <Page>
        {isMissing(detail.error) ? (
          <EmptyState icon={<UserRound />} title="No such account">
            It may have been deleted. <Link href="/app/admin/users">Back to users</Link>
          </EmptyState>
        ) : (
          <LoadError title="Couldn’t load this account" onRetry={() => void detail.refetch()} />
        )}
      </Page>
    );
  }
  const d = detail.data;
  const u = d.user;
  const p = d.profile;
  return (
    <Page>
      <Link
        href="/app/admin/users"
        className="-mb-4 inline-flex w-fit items-center gap-1.5 text-sm text-muted hover:text-fg"
      >
        <ArrowLeft className="h-4 w-4" /> All users
      </Link>
      <PageHeader title={u.full_name} description={u.email} actions={<Actions detail={d} />} />
      <SignInBadges user={u} />
      {!u.is_active && (
        <Callout tone="negative">
          This account is disabled: they can’t sign in. Their data is kept until you enable or
          delete it.
        </Callout>
      )}
      <AdminTabs />

      <StatGroup>
        <Stat
          label="Last seen"
          value={ago(u.last_seen_at)}
          note={u.last_seen_at ? dateTime(u.last_seen_at) : undefined}
        />
        <Stat label="Days active" value={n(u.active_days)} note="last 30 days" />
        <Stat
          label="Time on site"
          value={duration(u.engaged_seconds)}
          note={`${n(u.visits)} ${u.visits === 1 ? "visit" : "visits"}, last 30 days`}
        />
        <Stat label="AI uses" value={n(u.feature_uses)} note="last 30 days" />
      </StatGroup>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="p-5 sm:p-6">
          <CardHeader icon={<UserRound />} title="Account" />
          <div className="mt-5">
            <Facts
              rows={[
                ["Joined", dateTime(u.created_at)],
                ["Last sign-in", d.last_login_at ? dateTime(d.last_login_at) : "–"],
                ["Came from", u.source ?? "Unknown (before visit tracking)"],
                ["Open sessions", n(d.open_sessions)],
                ["Language", d.locale ?? "Browser default"],
                ["Weekly email", d.digest_enabled ? "On" : "Off"],
              ]}
            />
          </div>
        </Card>
        <Card className="p-5 sm:p-6">
          <CardHeader
            icon={<Package />}
            title="Profile"
            description="What they told us they trade."
          />
          <div className="mt-5">
            {p ? (
              <Facts
                rows={[
                  ["Trades from", p.exporter.name],
                  ["Role", p.role],
                  ["Goal", p.goal],
                  ["Products", p.products.map((x) => `${x.name} (${x.code})`).join("; ") || "–"],
                  ["Already sells to", p.current_markets.map((x) => x.name).join(", ") || "–"],
                  ["Updated", dateTime(p.updated_at)],
                ]}
              />
            ) : (
              <p className="text-sm text-muted">No profile yet: they haven’t finished setup.</p>
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="p-5 sm:p-6">
          <CardHeader icon={<CalendarDays />} title="Activity" />
          <div className="mt-5">
            <ActivityGrid days={d.active_days} />
          </div>
        </Card>
        <Card className="p-5 sm:p-6">
          <CardHeader
            icon={<MousePointerClick />}
            title="AI features"
            description="Last 30 days."
          />
          <div className="mt-5">
            <Ranked rows={d.feature_use} unit="times" />
          </div>
        </Card>
        <Card className="p-5 sm:p-6">
          <CardHeader icon={<Package />} title="What they made" description="All time." />
          <ul className="mt-5 flex flex-col divide-y divide-line text-sm">
            {d.made.map((m) => (
              <li key={m.name} className="flex justify-between gap-3 py-1.5">
                <span className="text-muted">{m.name}</span>
                <span className="tabular-nums">{n(m.count)}</span>
              </li>
            ))}
            {d.pipeline.map((s) => (
              <li key={s.name} className="flex justify-between gap-3 py-1.5 pl-3 text-xs">
                <span className="text-subtle">Pipeline: {STAGE_LABEL[s.name] ?? s.name}</span>
                <span className="text-muted tabular-nums">{n(s.count)}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <div className="p-5 pb-3 sm:p-6 sm:pb-3">
          <CardHeader
            icon={<Compass />}
            title="Visits"
            description="Their latest 20 visits. Open one to see the pages in order."
          />
        </div>
        {d.visits.length ? (
          d.visits.map((v) => <VisitRow key={v.id} visit={v} showUser={false} />)
        ) : (
          <p className="px-5 pb-5 text-sm text-muted sm:px-6">
            No visits recorded yet (visit tracking started on 27 Nov 2026, and “Do Not Track”
            browsers are never counted).
          </p>
        )}
      </Card>

      {d.history.length > 0 && (
        <Card className="p-5 sm:p-6">
          <CardHeader icon={<History />} title="Admin changes" />
          <ul className="mt-4 flex flex-col divide-y divide-line text-sm">
            {d.history.map((h) => (
              <li
                key={`${h.created_at}-${h.action}`}
                className="flex flex-wrap justify-between gap-2 py-2"
              >
                <span>{ACTION_LABEL[h.action] ?? h.action}</span>
                <span className="text-muted">
                  {h.admin_email} · {dateTime(h.created_at)}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </Page>
  );
}
