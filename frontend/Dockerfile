# Build context: frontend/
#   docker build --build-arg API_INTERNAL_URL=http://api:8000 frontend
#
# The build stages run on the build machine's CPU even when the target is another
# architecture (e.g. ARM64 for EC2): the output is plain JavaScript, and building under
# emulation would take many times longer. Only the runtime stage is per-architecture.

FROM --platform=$BUILDPLATFORM node:22-alpine AS base
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
WORKDIR /app

# ---------- dependencies ----------
FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile

# ---------- build ----------
FROM base AS build
# Where /api/* is forwarded; baked into the build's routing table.
ARG API_INTERNAL_URL=http://localhost:8400
ENV API_INTERNAL_URL=$API_INTERNAL_URL
# Shown on the Terms and Privacy pages; baked in at build time.
ARG NEXT_PUBLIC_CONTACT_EMAIL=
ENV NEXT_PUBLIC_CONTACT_EMAIL=$NEXT_PUBLIC_CONTACT_EMAIL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build
# sharp (image optimisation for next/image) is the only native module Next traces in, and
# it is built for the build machine's CPU. The app doesn't use next/image, so drop it, then
# refuse to continue if any other CPU-specific binary slipped into the bundle.
RUN rm -rf .next/standalone/node_modules/.pnpm/@img+* .next/standalone/node_modules/@img \
 && if find .next/standalone -name '*.node' | grep -q .; then \
      echo "Native module found in the web bundle:"; find .next/standalone -name '*.node'; exit 1; \
    fi

# ---------- runtime ----------
FROM node:22-alpine AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static
COPY --from=build --chown=app:app /app/public ./public
USER app
EXPOSE 3000
CMD ["node", "server.js"]
