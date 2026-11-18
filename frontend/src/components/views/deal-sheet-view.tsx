"use client";

import {
  ArrowLeft,
  Building2,
  CalendarDays,
  Check,
  Globe,
  Link2,
  ListChecks,
  MapPinOff,
  Printer,
  Search,
  Ship,
  Target,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type ReactNode, use, useEffect, useState } from "react";

import { LoadError } from "@/components/markets/load-error";
import { replaceSearchParams } from "@/components/markets/url-state";
import { VerdictBadge } from "@/components/markets/verdict";
import { Badge, Callout } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardHeader, Page, PageHeader } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/empty";
import { Segmented } from "@/components/ui/segmented";
import {
  boxName,
  CONTAINER_OPTIONS,
  type ContainerKind,
  type FreightEstimate,
  useFreight,
  useShipping,
} from "@/lib/api/freight";
import { type LandedCost, useLandedCost } from "@/lib/api/landed-cost";
import {
  ApiError,
  type LeadsContent,
  type MarketDetail,
  useBrief,
  useLeads,
  useMarketDetail,
  useRequestLeads,
} from "@/lib/api/queries";
import { money, percent, signedPercent } from "@/lib/format";
import { track } from "@/lib/analytics";
import { parseKg, perKg, usd, weight } from "@/lib/money";
import { useExporter, withExporter } from "@/lib/use-exporter";

function Section({
  icon,
  title,
  description,
  children,
  action,
}: {
  icon: ReactNode;
  title: string;
  description?: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <Card className="break-inside-avoid p-5 sm:p-6">
      <CardHeader icon={icon} title={title} description={description} action={action} />
      <div className="mt-5">{children}</div>
    </Card>
  );
}

function Row({
  label,
  kg,
  order,
  strong = false,
  muted = false,
}: {
  label: ReactNode;
  kg: string;
  order?: string;
  strong?: boolean;
  muted?: boolean;
}) {
  return (
    <tr className={strong ? "font-semibold text-fg" : muted ? "text-subtle" : "text-muted"}>
      <td className="py-1.5 pr-3">{label}</td>
      <td className="py-1.5 text-right tabular-nums">{kg}</td>
      <td className="py-1.5 pl-4 text-right tabular-nums">{order ?? ""}</td>
    </tr>
  );
}

/** 0 -> "0%", 12.5 -> "12.5%", 12 -> "12%". */
const dutyText = (pct: number) => `${Number(pct.toFixed(1))}%`;

/** The highest FOB price per kg at which you still land below the rival. */
function priceToBeat(l: LandedCost, freightKg: number): number | null {
  const rival = l.rivals[0];
  const duty = (l.yours?.duty_pct ?? l.duties.yours.rate_pct) / 100;
  if (!rival) return null;
  const max =
    l.duty_base === "CIF"
      ? rival.landed_usd_kg / (1 + duty) - freightKg
      : (rival.landed_usd_kg - freightKg) / (1 + duty);
  return max > 0 ? max : null;
}

function Numbers({
  detail,
  freight,
  landed,
  price,
  usingMarketPrice,
  containers,
}: {
  detail: MarketDetail;
  freight: FreightEstimate;
  landed: LandedCost;
  price: number;
  usingMarketPrice: boolean;
  containers: number;
}) {
  const yours = landed.yours;
  if (!yours) return <Skeleton className="h-40" />;
  const kgPerBox = freight.kg_per_container;
  const orderKg = kgPerBox * containers;
  const arrivalKg = freight.after_arrival.typical / kgPerBox;
  const delivered = yours.landed_usd_kg + arrivalKg;
  const rival = landed.rivals[0];
  const beat = priceToBeat(landed, yours.freight_usd_kg);
  const market = landed.market_price_usd_kg;
  const order = (perKgValue: number) => usd(perKgValue * orderKg);
  const duty = landed.duties.yours;

  return (
    <div className="flex flex-col gap-5">
      <table className="w-full text-sm">
        <caption className="sr-only">Your cost per kg and per order</caption>
        <thead>
          <tr className="text-left text-xs text-subtle">
            <th scope="col" className="pb-2 font-medium">
              {detail.product.name}, {detail.exporter.name} → {detail.market.market.name}
            </th>
            <th scope="col" className="pb-2 text-right font-medium">
              Per kg
            </th>
            <th scope="col" className="pb-2 pl-4 text-right font-medium">
              {freight.container === "lcl"
                ? `Shared container (${weight(orderKg)})`
                : `${containers} × ${freight.container} (${weight(orderKg)})`}
            </th>
          </tr>
        </thead>
        <tbody className="border-t border-line">
          <Row
            label={usingMarketPrice ? "Price (FOB, market average)" : "Your price (FOB)"}
            kg={perKg(price)}
            order={order(price)}
          />
          <Row
            label={`+ Freight and insurance to ${freight.route.dest_port}`}
            kg={perKg(yours.freight_usd_kg)}
            order={order(yours.freight_usd_kg)}
          />
          <Row
            label={`+ Duty ${dutyText(duty.rate_pct)}${duty.scheme ? ` (${duty.scheme})` : ""}`}
            kg={perKg(yours.duty_usd_kg)}
            order={order(yours.duty_usd_kg)}
          />
          <Row
            label={`= Landed at ${freight.route.dest_port}`}
            kg={perKg(yours.landed_usd_kg)}
            order={order(yours.landed_usd_kg)}
            strong
          />
          <Row label="+ Port handling on arrival" kg={perKg(arrivalKg)} order={order(arrivalKg)} />
          <Row
            label="= Delivered to the buyer"
            kg={perKg(delivered)}
            order={order(delivered)}
            strong
          />
        </tbody>
        <tbody className="border-t border-line">
          {market !== null && (
            <Row
              label={`${detail.market.market.name} pays suppliers on average (FOB)`}
              kg={perKg(market)}
              order={order(market)}
              muted
            />
          )}
          {rival && (
            <Row
              label={`${rival.country.name} lands at`}
              kg={perKg(rival.landed_usd_kg)}
              order={order(rival.landed_usd_kg)}
              muted
            />
          )}
        </tbody>
      </table>

      <div className="grid gap-3 sm:grid-cols-2">
        {beat !== null && rival && (
          <Callout tone={price <= beat ? "positive" : "caution"}>
            <span className="block font-medium">Price to beat {rival.country.name}</span>
            Below <strong className="tabular-nums">{perKg(beat)}</strong> FOB you land cheaper than
            them in {detail.market.market.name}
            {usingMarketPrice
              ? "."
              : price <= beat
                ? `: you’re ${perKg(beat - price)} under.`
                : `: you’re ${perKg(price - beat)} over.`}
          </Callout>
        )}
        {market !== null && !usingMarketPrice && (
          <Callout tone={price <= market ? "positive" : "caution"}>
            <span className="block font-medium">Against the market price</span>
            Your price is{" "}
            <strong className="tabular-nums">{signedPercent(price / market - 1)}</strong> vs what{" "}
            {detail.market.market.name} pays on average.{" "}
            {price <= market
              ? "Room to compete on price."
              : "Compete on quality, speed or a niche."}
          </Callout>
        )}
      </div>
    </div>
  );
}

function Contacts({
  hs6,
  market,
  marketName,
  productName,
  tabHref,
}: {
  hs6: string;
  market: string;
  marketName: string;
  productName: string;
  tabHref: string;
}) {
  const leads = useLeads(hs6, market, "buyers");
  const request = useRequestLeads(hs6, market, "buyers");
  const status = leads.data?.status;
  const content: LeadsContent | null | undefined = leads.data?.content;

  if (leads.isPending) return <Skeleton className="h-24" />;
  if (status === "ready" && content) {
    const top = content.companies.slice(0, 6);
    return (
      <div className="flex flex-col gap-4">
        {top.length === 0 ? (
          <p className="text-sm text-muted">No companies were named on the pages we searched.</p>
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2">
            {top.map((c) => (
              <li key={c.name} className="rounded-xl border border-line p-3">
                <span className="flex flex-wrap items-center gap-2">
                  <span dir="auto" className="font-medium text-fg">
                    {c.name}
                  </span>
                  <Badge>{c.kind}</Badge>
                </span>
                <span className="mt-0.5 block text-xs text-muted">
                  {[c.city, c.handles].filter(Boolean).join(" · ")}
                </span>
                {c.website && (
                  <a
                    href={c.website}
                    target="_blank"
                    rel="noopener noreferrer nofollow"
                    className="mt-1 inline-flex items-center gap-1 text-xs text-brand hover:underline"
                  >
                    <Globe className="h-3 w-3" aria-hidden /> {c.website.replace("https://", "")}
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
        {content.events[0] && (
          <p className="flex items-center gap-2 text-sm text-muted">
            <CalendarDays className="h-4 w-4 shrink-0 text-brand" aria-hidden />
            Meet them at {content.events[0].name}
            {[content.events[0].city, content.events[0].when].filter(Boolean).length > 0 &&
              ` (${[content.events[0].city, content.events[0].when].filter(Boolean).join(", ")})`}
          </p>
        )}
        <Link href={tabHref} className="no-print text-sm font-medium text-brand hover:underline">
          All {content.companies.length} companies, sources and email drafts →
        </Link>
      </div>
    );
  }
  return (
    <div className="flex flex-col items-start gap-3 rounded-2xl border border-dashed border-line-strong/60 p-4 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-muted">
        {status === "pending"
          ? "Searching directories and company sites…"
          : status === "failed"
            ? (leads.data?.error ?? "The last search didn’t finish.")
            : `Find importers and distributors of ${productName} in ${marketName}.`}
      </p>
      {status !== "pending" && (
        <Button
          variant="secondary"
          size="sm"
          className="no-print shrink-0"
          disabled={request.isPending}
          onClick={() => request.mutate()}
        >
          <Search /> Find buyers
        </Button>
      )}
      {request.isError && <p className="text-sm text-negative">{request.error.message}</p>}
    </div>
  );
}

function Steps({
  detail,
  freight,
  landed,
  events,
}: {
  detail: MarketDetail;
  freight: FreightEstimate | null | undefined;
  landed: LandedCost | undefined;
  events: LeadsContent["events"];
}) {
  const brief = useBrief(detail.exporter.code, detail.product.hs6, detail.market.market.code);
  const roadmap = brief.data?.status === "ready" ? brief.data.content?.roadmap : undefined;
  const market = detail.market.market.name;
  const duty = landed?.duties.yours;
  const steps: { title: string; detail: string }[] = roadmap?.length
    ? roadmap
    : [
        {
          title: "Set your price",
          detail:
            "Use the numbers above: stay under the price to beat, or have a clear reason (quality, speed, a niche) to be above it.",
        },
        {
          title: "Get two or three freight quotes",
          detail: freight
            ? `Ask forwarders for ${boxName(freight.container)}, ${freight.route.origin_port} → ${freight.route.dest_port}. Expect about ${usd(freight.to_port.low)}–${usd(freight.to_port.high)} to the port.`
            : "Ask forwarders for a container rate to the market's main port.",
        },
        {
          title: "Confirm duty and papers",
          detail: duty
            ? `${dutyText(duty.rate_pct)} duty${duty.scheme ? ` under ${duty.scheme}: you’ll need the certificate of origin it requires` : ""}. Check labelling and product rules for ${market} with your chamber of commerce.`
            : `Check duty, labelling and product rules for ${market} with your chamber of commerce.`,
        },
        {
          title: "Contact five buyers",
          detail:
            "Send a short email with your catalogue and price list; offer samples to those who reply.",
        },
        {
          title: events[0] ? `Meet buyers at ${events[0].name}` : "Meet buyers in person",
          detail: events[0]
            ? `${[events[0].city, events[0].when].filter(Boolean).join(", ") || "See the fair's site for dates"}. Book meetings before you go.`
            : `Look for trade fairs in ${market} for your product, and book meetings before you go.`,
        },
      ];
  return (
    <ol className="flex flex-col gap-4">
      {steps.map((step, i) => (
        <li key={step.title} className="flex gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-soft text-xs font-semibold text-brand tabular-nums">
            {i + 1}
          </span>
          <span dir="auto">
            <span className="block text-sm font-medium text-fg">{step.title}</span>
            <span className="block text-sm text-muted">{step.detail}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

/** One page to decide and act: the opportunity, your numbers, the route, buyers, next steps. */
export function DealSheetView({ params }: { params: Promise<{ hs6: string; market: string }> }) {
  const { hs6, market } = use(params);
  const code = market.toUpperCase();
  const search = useSearchParams();
  const override = search.get("exporter");
  const exporter = useExporter();
  const detail = useMarketDetail(exporter.code, hs6, code);
  const shipping = useShipping();

  const priceParam = Number(search.get("price"));
  const price = priceParam > 0 && priceParam <= 10_000 ? priceParam : null;
  const countParam = Number(search.get("n"));
  const shared = shipping.container === "lcl";
  const containers =
    !shared && Number.isInteger(countParam) && countParam >= 1 && countParam <= 100
      ? countParam
      : 1;
  const [priceText, setPriceText] = useState(price ? String(price) : "");
  const [orderText, setOrderText] = useState(shared && shipping.load ? String(shipping.load) : "");
  const { setLoad } = shipping;

  // The order size, when sharing a container; empty means a typical small order.
  useEffect(() => {
    if (!shared) return;
    const timer = setTimeout(() => {
      const kg = orderText.trim() ? parseKg(orderText) : null;
      if (!orderText.trim() || (kg !== null && kg > 0 && kg <= 30_000)) setLoad(kg);
    }, 500);
    return () => clearTimeout(timer);
  }, [orderText, shared, setLoad]);

  function pickContainer(next: ContainerKind) {
    if ((next === "lcl") !== shared) {
      setOrderText("");
      replaceSearchParams({ load: null, n: null });
    }
    shipping.setContainer(next);
  }
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      const value = Number(priceText.replace(/[$,\s]/g, ""));
      replaceSearchParams({ price: value > 0 && value <= 10_000 ? String(value) : null });
    }, 400);
    return () => clearTimeout(timer);
  }, [priceText]);

  const m = detail.data?.market;
  const marketPrice = m?.market_unit_price_usd_kg ?? undefined;
  const used = price ?? marketPrice;
  const freight = useFreight(exporter.code, code, hs6, shipping.container, shipping.load, used);
  const freightKg = freight.data?.to_port_usd_kg.typical;
  const landed = useLandedCost(
    exporter.code,
    hs6,
    code,
    used,
    freightKg !== undefined ? { usdKg: freightKg } : null,
  );
  const leads = useLeads(hs6, code, "buyers");
  const marketHref = withExporter(`/app/markets/${hs6}/${code}`, override);

  if (exporter.pending || (exporter.code && detail.isPending)) {
    return (
      <Page>
        <Skeleton className="h-24" />
        <Skeleton className="h-64" />
      </Page>
    );
  }
  if (!detail.data || !m) {
    const missing = detail.error instanceof ApiError && detail.error.status === 404;
    return (
      <Page>
        {missing || !exporter.code ? (
          <EmptyState icon={<MapPinOff />} title="No deal sheet for this market">
            Deal sheets are made for ranked markets of your products.
          </EmptyState>
        ) : (
          <LoadError title="Couldn’t load this market" onRetry={() => void detail.refetch()} />
        )}
      </Page>
    );
  }
  const d = detail.data;

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      track("deal_sheet_copy_link");
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  const today = new Date().toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <Page className="gap-5">
      <PageHeader
        eyebrow={
          <Link
            href={marketHref}
            className="no-print inline-flex items-center gap-1.5 rounded-lg text-sm text-muted hover:text-fg"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden /> {m.market.name} for {d.product.name}
          </Link>
        }
        title={`Deal sheet: ${d.product.name} to ${m.market.name}`}
        description={`From ${d.exporter.name} · ${today} · customs data ${d.data.start_year}–${d.data.end_year}`}
        actions={
          <div className="no-print flex gap-2">
            <Button variant="secondary" onClick={() => void copyLink()}>
              {copied ? <Check /> : <Link2 />} {copied ? "Copied" : "Copy link"}
            </Button>
            <Button
              onClick={() => {
                track("deal_sheet_print");
                window.print();
              }}
            >
              <Printer /> Print / PDF
            </Button>
          </div>
        }
      />

      <Section icon={<Target />} title="The opportunity">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <span className="self-start">
              <VerdictBadge verdict={m.verdict} />
            </span>
            <p className="text-sm leading-6 text-muted">{m.verdict.summary}</p>
          </div>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Market size", `${money(m.market_imports_usd)}`, `imports in ${d.data.end_year}`],
              [
                "Growth a year",
                signedPercent(m.import_growth_3y),
                `${d.data.start_year}–${d.data.end_year}`,
              ],
              [
                `${d.exporter.name}’s share`,
                percent(m.exporter_share, { floor: true }),
                `rank #${m.rank}`,
              ],
              [
                "Main rival",
                m.top_rival?.name ?? "None",
                m.top_rival_share !== null
                  ? `holds ${percent(m.top_rival_share, { floor: true })}`
                  : "",
              ],
            ].map(([label, value, note]) => (
              <div key={label} className="rounded-xl bg-surface-2/60 p-3">
                <dt className="text-xs text-muted">{label}</dt>
                <dd className="mt-1 text-lg font-semibold">{value}</dd>
                <dd className="text-xs text-subtle">{note}</dd>
              </div>
            ))}
          </dl>
        </div>
      </Section>

      <Section
        icon={<Wallet />}
        title="Your numbers"
        description="Your price, plus shipping and duty, against what the market pays and your main rival."
      >
        <div className="no-print mb-5 flex flex-wrap items-end gap-x-5 gap-y-3">
          <label className="flex flex-col gap-1 text-xs text-muted">
            Your price (FOB, USD per kg)
            <input
              inputMode="decimal"
              value={priceText}
              onChange={(e) => setPriceText(e.target.value)}
              placeholder={marketPrice ? marketPrice.toFixed(2) : "5.00"}
              className="h-10 w-36 rounded-lg border border-line bg-surface px-3 text-base text-fg tabular-nums outline-none focus:border-brand/60 focus:ring-4 focus:ring-brand/10 sm:text-sm"
            />
          </label>
          {shared ? (
            <label className="flex flex-col gap-1 text-xs text-muted">
              Order size (kg)
              <input
                inputMode="decimal"
                value={orderText}
                onChange={(e) => setOrderText(e.target.value)}
                placeholder={
                  freight.data ? String(Math.round(freight.data.kg_per_container)) : "1000"
                }
                className="h-10 w-28 rounded-lg border border-line bg-surface px-3 text-base text-fg tabular-nums outline-none focus:border-brand/60 focus:ring-4 focus:ring-brand/10 sm:text-sm"
              />
            </label>
          ) : (
            <label className="flex flex-col gap-1 text-xs text-muted">
              Containers per order
              <input
                type="number"
                min={1}
                max={100}
                value={containers}
                onChange={(e) =>
                  replaceSearchParams({ n: Number(e.target.value) > 1 ? e.target.value : null })
                }
                className="h-10 w-24 rounded-lg border border-line bg-surface px-3 text-base text-fg tabular-nums outline-none focus:border-brand/60 focus:ring-4 focus:ring-brand/10 sm:text-sm"
              />
            </label>
          )}
          <Segmented
            label="Container size"
            value={shipping.container}
            onChange={pickContainer}
            items={CONTAINER_OPTIONS}
          />
        </div>
        {!used ? (
          <p className="text-sm text-muted">Enter your price per kg to see your numbers.</p>
        ) : freight.data === null ? (
          <p className="text-sm text-muted">We don’t have a shipping route for this market yet.</p>
        ) : !freight.data || !landed.data ? (
          landed.isError ? (
            <p className="text-sm text-muted">
              Duty data for this market isn’t available right now.
            </p>
          ) : (
            <Skeleton className="h-48" />
          )
        ) : (
          <>
            {!price && (
              <p className="mb-4 text-sm text-muted">
                Showing the market’s average price, {perKg(used)}. Enter yours above.
              </p>
            )}
            <Numbers
              detail={d}
              freight={freight.data}
              landed={landed.data}
              price={used}
              usingMarketPrice={!price}
              containers={containers}
            />
          </>
        )}
      </Section>

      {freight.data && (
        <Section
          icon={<Ship />}
          title="Getting it there"
          action={
            <ButtonLink
              href={`${marketHref}?tab=prices`}
              variant="ghost"
              size="sm"
              className="no-print"
            >
              Full breakdown
            </ButtonLink>
          }
        >
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Route", `${freight.data.route.origin_port} → ${freight.data.route.dest_port}`],
              ["Time", `${freight.data.route.days_low}–${freight.data.route.days_high} days`],
              [
                shared ? "Your shipment" : `Per ${freight.data.container}`,
                `${usd(freight.data.total.low)}–${usd(freight.data.total.high)}`,
              ],
              [
                "Load",
                shared
                  ? `${weight(freight.data.kg_per_container)}, about ${freight.data.volume_m3} m³`
                  : `${weight(freight.data.kg_per_container)} per container`,
              ],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl bg-surface-2/60 p-3">
                <dt className="text-xs text-muted">{label}</dt>
                <dd className="mt-1 text-sm font-semibold">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-xs text-subtle">
            All-in to the buyer, low to high. An estimate from distance, fuel (Brent $
            {freight.data.fuel.brent_usd.toFixed(0)}) and typical port fees, not a quote.
          </p>
        </Section>
      )}

      <Section icon={<Building2 />} title={`Who to contact in ${m.market.name}`}>
        <Contacts
          hs6={hs6}
          market={code}
          marketName={m.market.name}
          productName={d.product.name}
          tabHref={`${marketHref}?tab=buyers`}
        />
      </Section>

      <Section icon={<ListChecks />} title="Next steps">
        <Steps
          detail={d}
          freight={freight.data}
          landed={landed.data}
          events={leads.data?.content?.events ?? []}
        />
      </Section>

      <p className="text-xs leading-5 text-subtle">
        Market figures: customs data (CEPII BACI) {d.data.start_year}–{d.data.end_year}. Duties:
        WITS/TRAINS and national tariffs. Shipping: our estimate, not a quote. Companies: found on
        the web and named on the linked pages; check them before sending samples or paying.
      </p>
    </Page>
  );
}
