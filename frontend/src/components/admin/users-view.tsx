"use client";

import { FlaskConical, Lock, Search, Users } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AdminTabs, ago, countryName, duration, n, shortDay } from "@/components/admin/parts";
import { LoadError } from "@/components/markets/load-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { inputClass } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import { Tabs } from "@/components/ui/tabs";
import { type UserRow, type UsersQuery, useAdminUsers } from "@/lib/api/admin";
import { isMissing, useCountries } from "@/lib/api/queries";

type Segment = NonNullable<UsersQuery["segment"]>;
type Status = NonNullable<UsersQuery["status"]>;
type Sort = NonNullable<UsersQuery["sort"]>;

const STATUS: { value: Status; label: string }[] = [
  { value: "any", label: "Everyone" },
  { value: "active", label: "Active this week" },
  { value: "inactive", label: "Not seen this week" },
  { value: "no_profile", label: "No profile yet" },
  { value: "unverified", label: "Email not verified" },
  { value: "disabled", label: "Disabled" },
];
const SORTS: { value: Sort; label: string }[] = [
  { value: "joined", label: "Newest" },
  { value: "last_seen", label: "Last seen" },
  { value: "most_active", label: "Most active" },
  { value: "name", label: "Name" },
];
const pick = <T extends string>(value: string | null, options: { value: T }[], fallback: T) =>
  options.some((o) => o.value === value) ? (value as T) : fallback;

export function SignInBadges({ user }: { user: UserRow }) {
  return (
    <span className="flex flex-wrap gap-1">
      {!user.is_active && <Badge tone="negative">Disabled</Badge>}
      {user.is_admin && <Badge tone="brand">Admin</Badge>}
      {user.is_test && <Badge tone="caution">Test</Badge>}
      <Badge>
        {user.sign_in === "both"
          ? "Google + password"
          : user.sign_in === "google"
            ? "Google"
            : "Password"}
      </Badge>
      {!user.email_verified && <Badge tone="caution">Unverified</Badge>}
    </span>
  );
}

/** Every account: who they are, where they came from, and how much they use the app. */
export function UsersView() {
  const search = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const segment = pick<Segment>(
    search.get("segment"),
    [{ value: "real" }, { value: "test" }, { value: "all" }],
    "real",
  );
  const status = pick(search.get("status"), STATUS, "any");
  const sort = pick(search.get("sort"), SORTS, "joined");
  const page = Math.max(1, Number(search.get("page")) || 1);
  const q = search.get("q") ?? "";
  const [text, setText] = useState(q);
  const users = useAdminUsers({ segment, status, sort, page, q });
  const countries = useCountries();
  const countryNames = useMemo(
    () => new Map((countries.data ?? []).map((c) => [c.code, c.name])),
    [countries.data],
  );

  function set(changes: Record<string, string | null>) {
    const next = new URLSearchParams(search);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    if (!("page" in changes)) next.delete("page");
    router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
  }

  useEffect(() => {
    if (text.trim() === q) return;
    const timer = setTimeout(() => set({ q: text.trim() || null }), 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only the typed text drives this
  }, [text]);

  if (users.isError && isMissing(users.error)) {
    return (
      <Page>
        <EmptyState icon={<Lock />} title="Not available">
          This page is for the site’s admins.
        </EmptyState>
      </Page>
    );
  }
  const data = users.data;
  const counts = data?.counts;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1;

  return (
    <Page>
      <PageHeader
        title="Users"
        description="Everyone with an account. Test and demo accounts are kept in their own tab and left out of the numbers."
      />
      <AdminTabs />
      <Tabs
        label="Accounts"
        value={segment}
        onChange={(v) => set({ segment: v === "real" ? null : v })}
        items={[
          {
            value: "real",
            icon: <Users />,
            label: `Real users${counts ? ` (${n(counts.real)})` : ""}`,
          },
          {
            value: "test",
            icon: <FlaskConical />,
            label: `Test & demo${counts ? ` (${n(counts.test)})` : ""}`,
          },
          { value: "all", label: "All" },
        ]}
      />
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <label className="relative min-w-0 flex-1">
            <span className="sr-only">Search by name or email</span>
            <Search
              aria-hidden
              className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-subtle"
            />
            <input
              type="search"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Search by name or email"
              className={`${inputClass} pl-10`}
            />
          </label>
          <label className="flex shrink-0 items-center gap-2 text-sm text-muted">
            Sort
            <select
              value={sort}
              onChange={(e) => set({ sort: e.target.value === "joined" ? null : e.target.value })}
              className={`${inputClass} w-auto`}
            >
              {SORTS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <Segmented
          items={STATUS}
          value={status}
          onChange={(v) => set({ status: v === "any" ? null : v })}
          label="Filter"
        />
      </div>

      {users.isPending ? (
        <Skeleton className="h-96" />
      ) : !data ? (
        <LoadError title="Couldn’t load users" onRetry={() => void users.refetch()} />
      ) : data.users.length === 0 ? (
        <Card className="p-6">
          <EmptyState icon={<Users />} title="No one here">
            {q || status !== "any"
              ? "No account matches these filters."
              : segment === "test"
                ? "Mark an account as test or demo from its page to move it here."
                : "No accounts yet."}
          </EmptyState>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[56rem] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-subtle">
                  <th scope="col" className="px-4 py-3 font-medium sm:px-5">
                    User
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Trades from
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Came from
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Joined
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Last seen
                  </th>
                  <th scope="col" className="px-3 py-3 text-right font-medium">
                    Days active
                  </th>
                  <th scope="col" className="px-3 py-3 text-right font-medium">
                    Time on site
                  </th>
                  <th scope="col" className="px-4 py-3 text-right font-medium sm:px-5">
                    AI uses
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.users.map((u) => (
                  <tr key={u.id} className="border-b border-line last:border-0 hover:bg-surface-2">
                    <td className="max-w-[22rem] px-4 py-3 sm:px-5">
                      <Link
                        href={`/app/admin/users/${u.id}`}
                        className="block min-w-0 font-medium text-fg hover:text-brand"
                      >
                        <span className="block truncate">{u.full_name}</span>
                        <span className="block truncate text-xs font-normal text-muted">
                          {u.email}
                        </span>
                      </Link>
                      <div className="mt-1.5">
                        <SignInBadges user={u} />
                      </div>
                    </td>
                    <td className="px-3 py-3 text-muted">
                      {u.exporter ? (countryNames.get(u.exporter) ?? u.exporter) : "–"}
                      {u.goal && <span className="block text-xs text-subtle">{u.goal}</span>}
                    </td>
                    <td className="px-3 py-3 text-muted">
                      {u.source ?? "–"}
                      {u.country && (
                        <span className="block text-xs text-subtle">{countryName(u.country)}</span>
                      )}
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap text-muted tabular-nums">
                      {shortDay(u.created_at)}
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap text-muted">
                      {ago(u.last_seen_at)}
                    </td>
                    <td className="px-3 py-3 text-right text-muted tabular-nums">
                      {n(u.active_days)}
                    </td>
                    <td className="px-3 py-3 text-right text-muted tabular-nums">
                      {u.engaged_seconds ? duration(u.engaged_seconds) : "–"}
                    </td>
                    <td className="px-4 py-3 text-right text-muted tabular-nums sm:px-5">
                      {n(u.feature_uses)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm sm:px-5">
            <span className="text-muted tabular-nums">
              {n(data.total)} {data.total === 1 ? "account" : "accounts"} · last 30 days for
              activity
            </span>
            {pages > 1 && (
              <span className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => set({ page: String(page - 1) })}
                >
                  Previous
                </Button>
                <span className="text-muted tabular-nums">
                  {page} / {pages}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page >= pages}
                  onClick={() => set({ page: String(page + 1) })}
                >
                  Next
                </Button>
              </span>
            )}
          </div>
        </Card>
      )}
    </Page>
  );
}
