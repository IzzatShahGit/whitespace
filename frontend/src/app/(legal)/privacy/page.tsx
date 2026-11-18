import type { Metadata } from "next";

import { LegalPage, Section } from "@/components/legal/legal-page";

export const metadata: Metadata = { title: "Privacy policy · Whitespace" };

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy policy"
      intro="We collect what we need to run your account and nothing to sell. No advertising, no tracking cookies."
    >
      <Section title="What we keep">
        <ul>
          <li>
            <strong>Account:</strong> your name, email, and a scrambled (hashed) version of your
            password; or your Google account id if you sign in with Google.
          </li>
          <li>
            <strong>Profile:</strong> the country you trade from and the products you choose.
          </li>
          <li>
            <strong>What you create:</strong> questions to the guide and its answers, your watchlist
            and its alerts.
          </li>
          <li>
            <strong>Usage counts:</strong> how many times each page and a few buttons are used per
            day, and a count of unique visitors per day. A visitor is counted with a code that
            changes every day and can’t be traced back to you; we don’t store your IP address.
          </li>
          <li>
            <strong>Limits:</strong> how many AI questions, briefs and searches you used today, to
            keep the free service fair.
          </li>
        </ul>
      </Section>
      <Section title="Cookies">
        <p>
          Only the cookies that keep you signed in. Your light/dark theme choice stays in your
          browser. If your browser sends “Do Not Track” or Global Privacy Control, we don’t even
          count your page views.
        </p>
      </Section>
      <Section title="Who else sees data">
        <p>We use a few services to run Whitespace. They process data only to provide it:</p>
        <ul>
          <li>
            <strong>Hosting and database:</strong> our app host and Neon (Postgres).
          </li>
          <li>
            <strong>AI:</strong> Google Gemini, with Groq as a backup, writes answers, briefs and
            email drafts. They receive your question and the trade data needed to answer it, not
            your email address.
          </li>
          <li>
            <strong>Web search:</strong> Tavily searches for news, companies and trade fairs using
            product and country names only.
          </li>
          <li>
            <strong>Email:</strong> Google’s mail service delivers password-reset emails.
          </li>
          <li>
            <strong>Sign-in:</strong> Google, if you choose “Continue with Google”.
          </li>
        </ul>
        <p>We never sell or rent personal data, and we don’t share it for advertising.</p>
      </Section>
      <Section title="How long we keep it">
        <p>
          Your account data stays until you delete your account. Usage counts are kept for about a
          year. Company and market research we generate isn’t personal and is shared between users.
        </p>
      </Section>
      <Section title="Your choices">
        <ul>
          <li>See and change your name and password in Settings.</li>
          <li>
            Delete your account in Settings: your profile, conversations, watchlist and alerts are
            deleted straight away.
          </li>
          <li>Ask us for a copy of your data, or about anything on this page.</li>
        </ul>
      </Section>
      <Section title="Security">
        <p>
          Connections are encrypted, passwords are hashed with Argon2, sessions use secure httpOnly
          cookies, and reset links work once for 30 minutes.
        </p>
      </Section>
    </LegalPage>
  );
}
