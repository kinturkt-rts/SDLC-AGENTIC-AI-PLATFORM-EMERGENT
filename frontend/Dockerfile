# SDLC control-plane UI (Next.js standalone) + backend read bundle for /api/v1 routes.
# Build from monorepo root:
#   docker build -f frontend/Dockerfile -t sdlc-control-plane:local .

FROM node:20-alpine AS deps
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app/frontend
COPY --from=deps /app/frontend/node_modules ./node_modules
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app

RUN apk add --no-cache python3 py3-pip \
  && pip3 install --no-cache-dir --break-system-packages boto3 python-dotenv

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
ENV BACKEND_ROOT=/backend
ENV SDLC_PIPELINE_TRANSPORT=a2a

COPY --from=builder /app/frontend/public ./public
COPY --from=builder /app/frontend/.next/standalone ./
COPY --from=builder /app/frontend/.next/static ./.next/static

COPY backend/agents /backend/agents
COPY backend/config /backend/config
COPY backend/docs /backend/docs
COPY backend/scripts /backend/scripts
COPY backend/inputs /backend/inputs
COPY backend/a2a /backend/a2a

EXPOSE 3000
CMD ["node", "server.js"]
