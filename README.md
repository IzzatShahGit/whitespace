<div align="center">

# Whitespace

### Trade intelligence for exporters, built on a real data platform and grounded AI.

Whitespace processes **a million-plus rows of global customs data** into ranked export opportunities, then uses **source-checked AI agents** to turn each opportunity into a deal: the right HS code, the rules to meet, the buyers to call, whether they are safe to deal with, the landed cost, the quote and the shipping documents.

![Next.js](https://img.shields.io/badge/Next.js_16-000000?logo=nextdotjs&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?logo=langchain&logoColor=white)
![Polars](https://img.shields.io/badge/Polars-CD792C?logo=polars&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-FFF000?logo=duckdb&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL_16-4169E1?logo=postgresql&logoColor=white)
![pgvector](https://img.shields.io/badge/pgvector-hybrid_RAG-336791?logo=postgresql&logoColor=white)

<br/>

<img src="docs/screenshots/dashboard.png" alt="Whitespace dashboard: best next market, an opportunity map, the sales pipeline, open tenders and the AI guide" width="100%"/>

<br/>

| **1M+** | **5,384** | **24** | **4,776** | **87K+** | **9** | **400+** |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| supplier–market rows | HS6 products | exporting countries | sea routes | sanctioned names screened | languages | tests |

</div>

---

## How it works

```
┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
│ DATA       │    │ SCORE      │    │ AI AGENTS  │    │ TRUST      │    │ DEAL       │
│ customs,   │ ─► │ rank every │ ─► │ HS codes,  │ ─► │ sanctions, │ ─► │ landed     │
│ tariffs,   │    │ market for │    │ rules,     │    │ buyer, PO  │    │ cost,      │
│ freight,   │    │ a product  │    │ buyers,    │    │ and LC     │    │ quote,     │
│ sanctions  │    │            │    │ emails     │    │ checks     │    │ documents  │
└────────────┘    └────────────┘    └────────────┘    └────────────┘    └────────────┘
Data platform     Scoring model     Grounded AI       Rules in code     Product
```

<br/>

## 🧱 Data platform

A batch pipeline on a **medallion architecture** turns raw customs data into analysis-ready gold tables. The API reads those tables in milliseconds, with no heavy queries at request time.

```mermaid
flowchart LR
    S1[CEPII BACI<br/>~200 countries × 5,000 products] --> BR
    S2[Port list +<br/>searoute] --> BR
    BR[🥉 Bronze<br/>raw release, versioned] --> SI[🥈 Silver<br/>typed, cleaned Parquet]
    SI --> GO[🥇 Gold<br/>opportunity scores · supplier landscape<br/>unit prices · sea routes]
    GO -->|bulk load| PG[(PostgreSQL)]
    GO -->|descriptions + everyday names| EM[Gemini embeddings<br/>768-d, changed rows only]
    EM -->|pgvector| PG
    S3[Sanctions lists<br/>OFAC · UN · EU · UK] -->|daily job · checksum skip<br/>atomic swap per list| PG
    L1[Live APIs<br/>Eurostat · US Census · WITS<br/>HMRC · FRED · FX · TED] -->|cached on demand| PG
```

| Layer | What happens | Tech |
|---|---|---|
| **Bronze** | Versioned BACI releases kept exactly as published (≈350 MB) | Python, httpx |
| **Silver** | Typed, deduplicated, country codes harmonised, columnar (≈340 MB) | Polars, Parquet |
| **Gold** | Scores, supplier shares, unit prices and routes, compacted to ≈47 MB | Polars, DuckDB |
| **Enrich** | Every product embedded for meaning search; 87K+ sanctioned names normalised (legal forms stripped) and trigram-indexed for fuzzy matching | Gemini embeddings, pgvector, pg_trgm |
| **Serve** | Bulk-loaded tables, plus live sources cached with lifetimes that match how often each source updates | PostgreSQL 16, pg_trgm |

**Batch and live, combined.** Annual bilateral trade comes from the batch pipeline. Monthly imports (Eurostat Comext and US Census), tariffs (WITS-TRAINS and HMRC), the Brent oil price (FRED), exchange rates and EU tenders (TED) are fetched live, normalised to one shape and cached. The four official sanctions lists are refreshed by a daily job that skips unchanged files and swaps each list in atomically, so a check never sees a half-loaded list. Product embeddings are incremental: only new or changed text is sent, so re-runs are free and resumable under the embedding API's daily quota. The gold-table schemas live in a **shared package** that both the pipeline and the API import, so the two can never disagree about the data shape.

### The opportunity model

<img src="docs/screenshots/markets.png" alt="60 markets ranked for towels from Pakistan, with verdicts and an opportunity map" width="100%"/>

For exporter **E**, product **p** and market **M**, over four years of trade:

| Signal | Definition |
|---|---|
| **Growth** | CAGR of M's imports of p |
| **Displacement** | Share lost by M's largest supplier other than E |
| **Headroom** | 1 − E's current share of M |
| **Size** | M's total imports of p |

A market qualifies only if it imports **≥ $10M** of p a year and E has a **revealed comparative advantage ≥ 1**. The score is the mean percentile rank of the four signals. Including size stops one large shipment into a tiny market from outranking a large, steady one. Each score maps to a plain-language verdict, such as *Go for it*, *Grow your lead* or *Hard to break in*.

**Freight is modelled, not guessed.** Real sea-route distances between 4,776 port pairs, container rates indexed to Brent crude, an adjustment for backhaul on each lane, full-container and shared-container (LCL) pricing, and low / typical / high ranges.

<br/>

## 🤖 Grounded AI

Seven AI agents, with the brief and the guide built as **LangGraph** graphs. They share one rule: **a model may write, but code decides what is true.** Every number and every claim is checked against data or a cited source before a user sees it.

```mermaid
flowchart LR
    Q[Question] --> P[Plan<br/>templated searches]
    P --> R[Research<br/>web + local language]
    R --> X[Extract<br/>small model, cited claims]
    X --> W[Write<br/>main model]
    W --> C{Check<br/>in code}
    C -->|every figure traced| OK[✅ Shown]
    C -->|unsupported| D[❌ Removed and counted]
```

| Agent | What it does | How it stays honest |
|---|---|---|
| **Market brief** | Research → extract → write → check: a structured go-to-market brief | Every figure must trace to a measured fact or a cited claim; the rest is removed |
| **AI guide** (chat) | A tool-using agent with 9 data tools: best markets, market facts, monthly trends, duties, prices, sourcing | Numbers in the answer must appear in tool results; one repair pass, then marked *ungrounded* |
| **Market requirements** | Certificates, product rules and labelling for one lane | Requirement kept only if its quote appears word for word on the source page; official domains preferred |
| **Company leads** | Importers and distributors, found with searches in the local language | Lead kept only if the company name appears on the cited page |
| **Outreach and replies** | Drafts first-contact emails in the buyer's language; reads a pasted reply into asks, a deadline and the next pipeline stage | Any figure not in your own data, and any leftover placeholder, is flagged before sending; every ask must quote the reply word for word |
| **HS code finder** | Finds the six-digit code from a description or a photo, using hybrid RAG (below) | The model can pick only from retrieved candidates, checked in code; scored against an eval set |
| **PO and LC reader** | Reads a buyer's purchase order or letter of credit | SWIFT MT700 is parsed in code; any other value must quote the document; scanned pages are marked unverified |

<table>
<tr>
<td width="50%"><img src="docs/screenshots/requirements.png" alt="Requirements checklist, each rule backed by an official source"/></td>
<td width="50%"><img src="docs/screenshots/leads.png" alt="Company leads, each linked to the page it was found on"/></td>
</tr>
<tr>
<td align="center"><sub>Requirements: each rule quoted from an official source</sub></td>
<td align="center"><sub>Leads: each company linked to where it was found</sub></td>
</tr>
</table>

### 🔎 Hybrid RAG: finding the HS code

Exporters often don't know their product's customs code, and every other feature starts from it. The finder combines three retrievers, fuses them and lets a model choose only from what was retrieved.

```mermaid
flowchart LR
    IN[Description<br/>or photo] --> PH{Photo?}
    PH -->|yes| VI[Vision model<br/>describes it in customs terms]
    PH -->|no| Q[Query]
    VI --> Q
    Q --> N[Everyday names<br/>alias table]
    Q --> F[Customs wording<br/>Postgres full-text]
    Q --> E[Meaning<br/>pgvector cosine]
    N --> RRF[Reciprocal rank fusion<br/>top 15 candidates]
    F --> RRF
    E --> RRF
    RRF --> M[Model picks up to 3<br/>with reasons and the<br/>questions that decide]
    M --> C{In the<br/>candidate list?}
    C -->|yes| OK[✅ Shown with confidence]
    C -->|no| D[❌ Dropped]
```

- **Three kinds of match.** Everyday names catch "hoodie", full-text search catches customs wording, and embeddings catch meaning when no words overlap.
- **Rank fusion, not score tuning.** Reciprocal rank fusion merges the lists without calibrating scores across retrievers.
- **Keeps working when a service is down.** Without the embedding API, names and words still run. Without the model, the closest candidates are shown and labelled as such.
- **Measured, not assumed.** `make eval-hs` scores both retrieval (is the right code in the top candidates?) and the model's final pick against a 40-case labelled eval set, so every change to the finder can be checked before it ships. **Target: ≥ 92.5% first-pick accuracy and ≥ 95% top-3 recall.**

**Production LLM engineering:**
- **Two model tiers.** A small model extracts and a main model writes, so each step uses the cheapest model that can do it.
- **Key rotation and fallback.** Calls rotate round-robin across keys, a rate-limited key rests automatically, and Gemini falls back to Groq. Ollama runs everything offline for development.
- **Arithmetic in code.** "18 lakh", "2.5 crore" and "5 tons" are parsed deterministically, so the model never does the maths.
- **Cost control.** Token use is recorded per brief, results are cached and shared across users, and each user has daily caps.
- **No model where rules will do.** Sanctions, red flags, date rules and SWIFT parsing are plain code: free, instant and the same answer every time.

<br/>

## 🛡️ Trust and compliance

Before money moves, two checks answer *is this buyer real?* and *is this document safe to accept?* Both are built mainly from **fixed rules and free public data**, so the same input always gives the same answer, and every finding comes with its source.

```mermaid
flowchart LR
    B[Buyer name, website,<br/>email, VAT number] --> S[Sanctions<br/>OFAC · UN · EU · UK<br/>fuzzy trigram match]
    B --> R[Registers<br/>GLEIF · EU VIES]
    B --> DM[Domain<br/>age via RDAP · webmail<br/>· lookalike]
    B --> CT[Country risk]
    B --> TX[Email wording<br/>scam patterns]
    S --> V{Verdict}
    R --> V
    DM --> V
    CT --> V
    TX --> V
    V --> G[🟢 Green]
    V --> A[🟠 Amber: verify]
    V --> X[🔴 Red: stop]
```

| Check | What it does | How it stays honest |
|---|---|---|
| **Buyer check** | Screens a company against four sanctions lists, legal-entity and VAT registers, website age, email domain and the wording of their emails | Strong and possible matches are graded separately; generic words such as "trading" never match alone; it says what it can't tell you, such as whether they will pay |
| **PO and LC checker** | Reads a purchase order or letter of credit and compares every term with your quote | Flags soft clauses that let the buyer block payment, dates that leave too little time to ship (UCP 600), and a sanctioned issuing bank; nothing uploaded is stored |


<br/>

## 📦 From opportunity to shipment

<table>
<tr>
<td width="50%"><img src="docs/screenshots/deal-sheet.png" alt="Deal sheet with landed-cost breakdown"/></td>
<td width="50%"><img src="docs/screenshots/quote.png" alt="CIF quotation to a German buyer"/></td>
</tr>
<tr>
<td align="center"><sub>Deal sheet: the market case and landed cost on one shareable page</sub></td>
<td align="center"><sub>Quote: Incoterms-aware, with freight and insurance worked out</sub></td>
</tr>
</table>

<details>
<summary><b>See every feature</b></summary>

<br/>

**Discover**
- Markets ranked for any product, plus Compare, Browse, Niche and Grow-range views
- A Buy / Sourcing side for importers looking for suppliers
- Watchlists, with alerts when new monthly data moves a market

**Validate**
- HS code finder from a plain description or a product photo
- Import duties by partner country, including preferential rates such as GSP+
- AI market-requirements checklist that users tick off as they prepare

**Cost**
- Freight estimator for full and shared (LCL) containers, with the break-even volume between them
- Landed-cost receipt with live exchange rates

**Connect**
- AI company leads, with first emails drafted in the buyer's language
- Reply reader: paste a buyer's email to get their asks, deadline and a drafted answer, with the pipeline card updated
- Sales pipeline: stages, conversation history, follow-up reminders, weekly email digest
- Buyer check: sanctions, company registers, domain age and scam wording, with a red / amber / green verdict
- EU public tenders (TED) matched to your products through an HS-to-CPV mapping, with daily alerts

**Close and ship**
- Deal sheet with the numbers kept in the URL, so a shared link shows the same sheet, plus print to PDF
- Quotes for FOB, CFR, CIF and DAP, with gapless numbering
- PO and letter-of-credit checker that compares the buyer's terms with your quote
- Commercial invoice, packing list, statement on origin and REX-threshold warnings

**Platform**
- Email and password (Argon2) or Google sign-in, password reset, HTTP-only cookie sessions
- 9 languages, with right-to-left layouts for Urdu and Arabic
- First-party analytics and an admin console

</details>

<br/>

## 🏗️ Architecture

```mermaid
flowchart TB
    U[Browser] --> W[Next.js 16 · React 19<br/>9 languages · typed API client]
    W -->|/api proxy · first-party cookies| API[FastAPI<br/>async SQLAlchemy]

    API --> AI
    API --> RULES
    API --> EXT[Live APIs<br/>trade · tariffs · FX · TED<br/>GLEIF · VIES · RDAP]

    subgraph AI[AI layer]
        AG[Agents<br/>brief · guide · requirements<br/>leads · outreach · PO and LC reader]
        RAG[Hybrid RAG<br/>HS code finder]
    end

    subgraph RULES[Rules in code]
        BC[Buyer check<br/>sanctions · registers · domains]
        DR[Document rules<br/>MT700 · UCP 600 · soft clauses]
    end

    AI --> LLM[Gemini / Groq<br/>key rotation · fallback]

    subgraph DB[PostgreSQL 16]
        GOLD[(Gold tables<br/>scores · prices · routes)]
        APP[(App data<br/>pipeline · quotes · shipments)]
        TRG[(pg_trgm<br/>sanctioned names)]
        VEC[(pgvector<br/>product embeddings)]
    end

    API --> GOLD
    API --> APP
    RAG --> VEC
    BC --> TRG
    JOB[Lease-based scheduler<br/>alerts · reminders · digests<br/>sanctions refresh] --> DB
```

- **One typed contract, end to end.** The frontend's API client is generated from the backend's OpenAPI spec, so changing an endpoint breaks the frontend build, not production.
- **Correct under concurrency.** Quote and invoice numbers are gapless and allocated under row locks. Pipeline cards use version-checked writes. Scheduled jobs hold database leases. A model is never called while a row is locked.
- **Secure by default.** Argon2 password hashing, secure HTTP-only cookies, rate limits that trust only known proxy hops, HMAC-signed links, hardened response headers, uploaded documents checked in memory and never stored, and an API that is never exposed directly.
- **Built to run on free tiers.** A single ARM64 production image of about 140 MB that idles at about 150 MB of RAM, configured only by environment variables, so it is portable to any host.

| | |
|---|---|
| **Frontend** | Next.js 16 · React 19 · TypeScript · Tailwind CSS 4 · TanStack Query |
| **Backend** | FastAPI · SQLAlchemy 2 (async) · Alembic · Pydantic v2 |
| **Data** | Polars · DuckDB · Parquet · PostgreSQL 16 (pgvector, pg_trgm, full-text search) |
| **AI** | LangGraph · LangChain · Gemini (chat, vision, embeddings) · Groq · Ollama · Tavily · hybrid RAG |
| **Quality** | pytest · eval sets · Ruff · mypy · ESLint · GitHub Actions · Docker |

<br/>

## 🚀 Getting started

```bash
make env    # create .env, then add a free Google AI Studio key (GOOGLE_API_KEY_1)
make up     # start web, API and database in Docker
```

Open **http://localhost:3400** for the app or **http://localhost:8400/docs** for the API reference.

<details>
<summary><b>Local development, data pipeline and checks</b></summary>

<br/>

**Prerequisites:** Docker with Compose, [uv](https://docs.astral.sh/uv/), and Node.js 20.9+ with pnpm.

```bash
make install     # Python and frontend dependencies
make db          # Postgres only
make migrate     # apply migrations
make api         # API with hot reload on :8400
make web         # web app with hot reload on :3400

make check       # lint + typecheck + tests (what CI runs)
make gen-client  # regenerate frontend API types after changing an endpoint
make check-keys  # test every configured API key without printing it
make sanctions   # load the OFAC, UN, EU and UK sanctions lists (also refreshed daily)
make embed       # embed products for HS-code search (only new or changed ones)
make eval-hs     # score the HS-code finder (ARGS=--pick to include the AI step)
make help        # every command
```

**Optional keys** switch on their features: Groq (LLM fallback), Tavily (leads and requirements), US Census (US monthly data), Google OAuth and SMTP. `.env.example` lists every key.

**Repository layout**

```
frontend/   Next.js app: product UI, public pages, i18n
backend/    FastAPI: API, AI agents, integrations, jobs, migrations, evals
pipeline/   Data pipeline: bronze → silver → gold → load
shared/     Gold-table schemas shared by the pipeline and the API
deploy/     Production container build
docs/       Architecture decisions and screenshots
```

</details>

---

<div align="center">
<sub>Built entirely on public data. Scores describe where a country competes well. They are not a guarantee for any single firm.</sub>
</div>
