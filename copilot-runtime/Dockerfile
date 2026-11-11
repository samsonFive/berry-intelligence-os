# Build from the repository root: docker build -f copilot-runtime/Dockerfile .
FROM node:24.22.1-bookworm-slim

WORKDIR /app/copilot-runtime
RUN npm install --global pnpm@11.25.0 --ignore-scripts
COPY copilot-runtime/package.json copilot-runtime/pnpm-lock.yaml copilot-runtime/pnpm-workspace.yaml ./
RUN pnpm install --prod --frozen-lockfile --ignore-scripts
COPY copilot-runtime/server.mjs ./server.mjs

USER node
ENV BIOS_COPILOT_PORT=8200
EXPOSE 8200
CMD ["node", "server.mjs"]
