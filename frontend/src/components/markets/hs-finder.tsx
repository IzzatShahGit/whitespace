"use client";

import { Camera, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { type FormEvent, useId, useRef, useState } from "react";

import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/empty";
import { inputClass } from "@/components/ui/field";
import { type HsPick, useIdentifyProduct } from "@/lib/api/hs";
import { capitalize, shortProductName } from "@/lib/format";
import { useT } from "@/lib/i18n";

const CONFIDENCE: Record<HsPick["confidence"], Tone> = {
  high: "positive",
  medium: "caution",
  low: "neutral",
};

export type PickedProduct = { hs6: string; description: string; name: string };

/** Describe a product (or add a photo) and get likely HS codes, each with why. With
 * `onPick` a code can be used right away; otherwise each links to its markets. */
export function HsFinder({
  initial = "",
  onPick,
}: {
  initial?: string;
  onPick?: (product: PickedProduct) => void;
}) {
  const t = useT();
  const id = useId();
  const find = useIdentifyProduct();
  const input = useRef<HTMLInputElement>(null);
  const [text, setText] = useState(initial);
  const [photo, setPhoto] = useState<File | undefined>();
  const result = find.data;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!photo && text.trim().length < 3) return;
    find.mutate({ description: text.trim() || undefined, photo });
  }

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4 shadow-card">
      <form onSubmit={submit} className="flex flex-col gap-2">
        <label htmlFor={`${id}-text`} className="text-sm font-medium text-fg">
          {t("hs.describe")}
        </label>
        <textarea
          id={`${id}-text`}
          value={text}
          rows={2}
          maxLength={600}
          dir="auto"
          onChange={(e) => setText(e.target.value)}
          placeholder={t("hs.placeholder")}
          className={`${inputClass} h-auto py-2.5 text-sm`}
        />
        <input
          ref={input}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          capture="environment"
          className="sr-only"
          aria-label={t("hs.photo")}
          onChange={(e) => setPhoto(e.target.files?.[0])}
        />
        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" size="sm" disabled={find.isPending}>
            <Sparkles /> {find.isPending ? t("hs.finding") : t("hs.find")}
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => input.current?.click()}>
            <Camera /> {photo ? t("hs.otherPhoto") : t("hs.photo")}
          </Button>
          {photo && (
            <span className="inline-flex items-center gap-1 text-xs text-muted">
              {photo.name}
              <button
                type="button"
                aria-label={t("common.remove")}
                onClick={() => {
                  setPhoto(undefined);
                  if (input.current) input.current.value = "";
                }}
              >
                <X className="h-3.5 w-3.5" aria-hidden />
              </button>
            </span>
          )}
        </div>
        {find.isError && (
          <p role="alert" className="text-xs text-negative">
            {find.error.message}
          </p>
        )}
      </form>

      {find.isPending && <Skeleton className="h-28" />}
      {result && !find.isPending && (
        <div className="flex flex-col gap-3">
          {result.from_photo && (
            <p className="text-xs text-muted">{t("hs.seen", { text: result.query })}</p>
          )}
          {result.picks.length === 0 ? (
            <p className="text-sm text-muted">{t("hs.nothing")}</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {result.picks.map((p) => (
                <li key={p.hs6} className="flex flex-col gap-1.5 rounded-xl bg-surface-2/60 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-medium text-fg">
                      {capitalize(p.name)}{" "}
                      <span className="text-subtle tabular-nums">HS {p.hs6}</span>
                    </span>
                    <Badge tone={CONFIDENCE[p.confidence]}>
                      {t(`hs.confidence.${p.confidence}`)}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted">{shortProductName(p.description)}</p>
                  <p className="text-xs text-fg/80">{p.why}</p>
                  {onPick ? (
                    <Button
                      size="sm"
                      variant="secondary"
                      className="self-start"
                      onClick={() =>
                        onPick({ hs6: p.hs6, description: p.description, name: p.name })
                      }
                    >
                      {t("hs.use")}
                    </Button>
                  ) : (
                    <Link
                      href={`/app/markets/${p.hs6}`}
                      className="text-xs text-brand hover:underline"
                    >
                      {t("hs.markets")}
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          )}
          {result.questions.length > 0 && (
            <div className="text-xs text-muted">
              <p className="font-medium text-fg">{t("hs.questions")}</p>
              <ul className="mt-1 list-disc ps-5">
                {result.questions.map((q) => (
                  <li key={q}>{q}</li>
                ))}
              </ul>
            </div>
          )}
          {result.others.length > 0 && (
            <details className="text-xs text-muted">
              <summary className="cursor-pointer">
                {t("hs.others", { count: result.others.length })}
              </summary>
              <ul className="mt-1 flex flex-col gap-1 ps-4">
                {result.others.map((o) => (
                  <li key={o.hs6}>
                    {onPick ? (
                      <button
                        type="button"
                        className="text-start hover:text-fg hover:underline"
                        onClick={() =>
                          onPick({ hs6: o.hs6, description: o.description, name: o.name })
                        }
                      >
                        HS {o.hs6} · {shortProductName(o.description)}
                      </button>
                    ) : (
                      <Link
                        href={`/app/markets/${o.hs6}`}
                        className="hover:text-fg hover:underline"
                      >
                        HS {o.hs6} · {shortProductName(o.description)}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </details>
          )}
          <p className="text-xs text-subtle">
            {result.method === "search" ? `${t("hs.searchOnly")} ` : ""}
            {t("hs.note")}
          </p>
        </div>
      )}
    </div>
  );
}
