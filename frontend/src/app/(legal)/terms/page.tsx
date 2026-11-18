import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage, Section } from "@/components/legal/legal-page";

export const metadata: Metadata = { title: "Terms of use · Whitespace" };

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms of use"
      intro="Whitespace helps you find export markets, suppliers and buyers from public trade data. These terms explain what you can expect from us and what we expect from you."
    >
      <Section title="Guidance, not advice">
        <p>
          Rankings, verdicts, prices, duties, shipping estimates and AI answers are{" "}
          <strong>guidance to help you decide where to look</strong>. They are not legal, financial,
          tax or customs advice, and not quotes. Trade data is historical and averaged; duties and
          freight rates change. Check anything you rely on with the relevant authority, a customs
          broker or freight forwarder before you commit money.
        </p>
      </Section>
      <Section title="Companies and events">
        <p>
          The companies and trade fairs we list are found on public web pages, and each links to the
          page that names it. Being listed is not an endorsement, and we don’t verify who they are,
          how they trade or whether they’ll pay. Do your own checks before sending samples, goods or
          money.
        </p>
      </Section>
      <Section title="Your account">
        <ul>
          <li>Give a real email address and keep your password to yourself.</li>
          <li>One person per account. You’re responsible for what happens under it.</li>
          <li>
            You can delete your account at any time in Settings; that removes your profile,
            conversations and watchlist.
          </li>
        </ul>
      </Section>
      <Section title="Fair use">
        <p>Please don’t:</p>
        <ul>
          <li>scrape or bulk-download the data or use automated tools against the service;</li>
          <li>try to get around daily limits, break security or reach other people’s data;</li>
          <li>use the service, or the emails it drafts, for spam, fraud or anything unlawful.</li>
        </ul>
        <p>We may suspend accounts that do.</p>
      </Section>
      <Section title="The service">
        <p>
          Whitespace is free while in early access and provided “as is”. We work to keep it accurate
          and available but can’t promise it will always be either. Features and limits may change.
          To the extent the law allows, we aren’t liable for losses that come from relying on the
          service or from it being unavailable.
        </p>
      </Section>
      <Section title="Data sources">
        <p>
          Trade figures come from CEPII BACI (built on UN Comtrade), Eurostat and the US Census
          Bureau; duties from WITS-TRAINS and national tariffs. Their terms apply to those figures,
          and they are credited where the data appears.
        </p>
      </Section>
      <Section title="Changes">
        <p>
          If we change these terms in a way that matters, we’ll say so in the app before the change
          applies. See also our <Link href="/privacy">Privacy policy</Link>.
        </p>
      </Section>
    </LegalPage>
  );
}
