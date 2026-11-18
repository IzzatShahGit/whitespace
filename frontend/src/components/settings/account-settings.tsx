"use client";

import { KeyRound, MailCheck, Palette, Trash2, UserRound } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { ThemeSwitch } from "@/components/shell/topbar";
import { api } from "@/lib/api/client";
import { keys, unwrap } from "@/lib/api/queries";
import { Callout } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/empty";
import { Field } from "@/components/ui/field";
import {
  type User,
  useChangePassword,
  useDeleteAccount,
  useMe,
  useUpdateMe,
} from "@/lib/api/queries";

function Saved({ show }: { show: boolean }) {
  return show ? <span className="pop-in text-sm text-positive">Saved</span> : null;
}

function NameCard({ user }: { user: User }) {
  const update = useUpdateMe();
  const [name, setName] = useState(user.full_name);
  const changed = name.trim() !== user.full_name && name.trim().length > 0;

  function submit(e: FormEvent) {
    e.preventDefault();
    if (changed) update.mutate(name.trim());
  }

  return (
    <Card className="p-5 sm:p-6">
      <CardHeader icon={<UserRound />} title="Profile" description="How we greet you." />
      <form onSubmit={submit} className="mt-5 grid gap-4 sm:grid-cols-2">
        <Field
          id="full-name"
          label="Full name"
          value={name}
          maxLength={120}
          onChange={(e) => setName(e.target.value)}
          autoComplete="name"
        />
        <Field id="email" label="Email" value={user.email} disabled hint="Your sign-in email." />
        <div className="flex items-center gap-3 sm:col-span-2">
          <Button type="submit" disabled={!changed || update.isPending}>
            {update.isPending ? "Saving…" : "Save name"}
          </Button>
          <Saved show={update.isSuccess && !changed} />
          {update.error && <span className="text-sm text-negative">{update.error.message}</span>}
        </div>
      </form>
    </Card>
  );
}

function PasswordCard({ user }: { user: User }) {
  const change = useChangePassword();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const tooShort = next.length > 0 && next.length < 8;

  function submit(e: FormEvent) {
    e.preventDefault();
    if (next.length < 8) return;
    change.mutate(
      { current_password: user.has_password ? current : null, new_password: next },
      {
        onSuccess: () => {
          setCurrent("");
          setNext("");
        },
      },
    );
  }

  return (
    <Card className="p-5 sm:p-6">
      <CardHeader
        icon={<KeyRound />}
        title={user.has_password ? "Password" : "Set a password"}
        description={
          user.has_password
            ? "Changing it signs you out on your other devices."
            : "You sign in with Google. Add a password to sign in with your email too."
        }
      />
      <form onSubmit={submit} className="mt-5 grid gap-4 sm:grid-cols-2">
        {user.has_password && (
          <Field
            id="current-password"
            label="Current password"
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        )}
        <Field
          id="new-password"
          label="New password"
          type="password"
          autoComplete="new-password"
          value={next}
          minLength={8}
          maxLength={128}
          error={tooShort ? "At least 8 characters" : undefined}
          onChange={(e) => setNext(e.target.value)}
        />
        <div className="flex items-center gap-3 sm:col-span-2">
          <Button
            type="submit"
            disabled={next.length < 8 || (user.has_password && !current) || change.isPending}
          >
            {change.isPending ? "Saving…" : "Update password"}
          </Button>
          <Saved show={change.isSuccess} />
          {change.error && <span className="text-sm text-negative">{change.error.message}</span>}
        </div>
      </form>
    </Card>
  );
}

/** The weekly email: off by default; turning it on confirms the address first. */
function DigestCard({ user }: { user: User }) {
  const client = useQueryClient();
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<{ tone: "positive" | "negative"; text: string }>();

  async function toggle(enabled: boolean) {
    setPending(true);
    setMessage(undefined);
    try {
      const out = await unwrap(api.POST("/api/v1/auth/digest", { body: { enabled } }));
      await client.invalidateQueries({ queryKey: keys.me });
      setMessage(
        out.verification_sent
          ? {
              tone: "positive",
              text: `We sent a link to ${user.email}. Open it to confirm your address; the weekly email starts then.`,
            }
          : { tone: "positive", text: enabled ? "Weekly email on." : "Weekly email off." },
      );
    } catch (error) {
      setMessage({ tone: "negative", text: (error as Error).message });
    } finally {
      setPending(false);
    }
  }

  return (
    <Card className="p-5 sm:p-6">
      <CardHeader
        icon={<MailCheck />}
        title="Weekly email"
        description="Monday mornings: follow-ups due, moves in your markets, checklists and trade fairs. Only when there’s something new."
      />
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Button
          variant={user.digest_enabled ? "secondary" : "primary"}
          disabled={pending}
          onClick={() => void toggle(!user.digest_enabled)}
        >
          {user.digest_enabled ? "Turn off" : "Turn on"}
        </Button>
        <span className="text-sm text-muted">
          {user.digest_enabled ? `On, to ${user.email}` : "Off"}
        </span>
      </div>
      {message && (
        <p
          role="status"
          className={`mt-3 text-sm ${message.tone === "positive" ? "text-positive" : "text-negative"}`}
        >
          {message.text}
        </p>
      )}
    </Card>
  );
}

function AppearanceCard() {
  return (
    <Card className="p-5 sm:p-6">
      <CardHeader
        icon={<Palette />}
        title="Appearance"
        description="Light, dark, or match your device."
      />
      <div className="mt-5 max-w-sm">
        <ThemeSwitch />
      </div>
    </Card>
  );
}

function DangerCard({ user }: { user: User }) {
  const router = useRouter();
  const remove = useDeleteAccount();
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    remove.mutate(user.has_password ? password : null, {
      onSuccess: () => {
        router.replace("/");
        router.refresh();
      },
    });
  }

  return (
    <Card className="border-negative/30 p-5 sm:p-6">
      <CardHeader
        icon={<Trash2 />}
        title="Delete account"
        description="Removes your account, preferences, conversations and watchlist. This can’t be undone."
      />
      {!confirming ? (
        <Button
          variant="secondary"
          className="mt-5 text-negative"
          onClick={() => setConfirming(true)}
        >
          Delete my account
        </Button>
      ) : (
        <form onSubmit={submit} className="pop-in mt-5 flex flex-col gap-4">
          <Callout tone="negative">
            Everything linked to {user.email} will be deleted permanently.
          </Callout>
          {user.has_password && (
            <Field
              id="delete-password"
              label="Confirm with your password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="max-w-sm"
            />
          )}
          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="submit"
              variant="danger"
              disabled={(user.has_password && !password) || remove.isPending}
            >
              {remove.isPending ? "Deleting…" : "Delete permanently"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
            {remove.error && <span className="text-sm text-negative">{remove.error.message}</span>}
          </div>
        </form>
      )}
    </Card>
  );
}

export function AccountSettings() {
  const me = useMe();
  if (!me.data) return <Skeleton className="h-64" />;
  return (
    <>
      <NameCard user={me.data} />
      <PasswordCard user={me.data} />
      <DigestCard user={me.data} />
      <AppearanceCard />
      <DangerCard user={me.data} />
    </>
  );
}
