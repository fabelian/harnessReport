FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund

FROM node:20-alpine AS builder
WORKDIR /app
# next.config.mjs reads NEXT_PUBLIC_BACKEND_URL inside rewrites(), which
# Next.js evaluates during `next build` and bakes into the build output.
# Railway forwards matching service variables as Docker build args when the
# Dockerfile declares them with ARG.
ARG NEXT_PUBLIC_BACKEND_URL
ENV NEXT_PUBLIC_BACKEND_URL=${NEXT_PUBLIC_BACKEND_URL}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/next.config.mjs ./next.config.mjs
EXPOSE 3000
# `next start` reads $PORT automatically (defaults to 3000), so Railway/Render
# injection works without extra plumbing.
CMD ["npm", "start"]
