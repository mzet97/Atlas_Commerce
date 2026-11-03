FROM node:22-slim
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0 PORT=3000 HOSTNAME=0.0.0.0
WORKDIR /srv
COPY package.json pnpm-lock.yaml* ./
RUN corepack enable && corepack prepare pnpm@11.1.3 --activate && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build
EXPOSE 3000
CMD ["pnpm", "start"]
