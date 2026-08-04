FROM node:22-alpine AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

FROM node:22-alpine
ENV NODE_ENV=production OUTBOARD_HOST=0.0.0.0 OUTBOARD_PORT=4323
WORKDIR /app
COPY --from=dependencies /app/node_modules ./node_modules
COPY --chown=node:node package.json server.mjs database.mjs worker.mjs source-import.mjs ./
COPY --chown=node:node public ./public
COPY --chown=node:node data ./data
USER node
EXPOSE 4323
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=5 \
  CMD wget -qO- http://127.0.0.1:4323/api/health >/dev/null || exit 1
CMD ["node", "server.mjs"]
