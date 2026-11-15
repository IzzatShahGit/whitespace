# Whitespace frontend

Next.js (App Router) + TypeScript + Tailwind.

```
src/
├── app/          routes (one folder per URL)
├── components/   reusable UI pieces
└── lib/
    ├── config.ts      public settings (NEXT_PUBLIC_*)
    └── api/           typed API client, types generated from the backend
```

## Commands

```bash
pnpm dev          # http://localhost:3400
pnpm lint
pnpm typecheck
pnpm build
```

After changing a backend endpoint, regenerate the API types from the repo root with `make gen-client`.

`NEXT_PUBLIC_API_URL` points the app at the API (default `http://localhost:8400`).
