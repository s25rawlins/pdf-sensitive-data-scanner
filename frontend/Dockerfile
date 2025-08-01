FROM node:18-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

RUN npm run build

# Production stage
FROM node:18-alpine

WORKDIR /app

RUN addgroup -g 1001 -S nodejs
RUN adduser -S nextjs -u 1001

COPY --from=builder --chown=nextjs:nodejs /app/.next ./.next
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/package*.json ./
COPY --from=builder --chown=nextjs:nodejs /app/next.config.ts ./
COPY --from=builder --chown=nextjs:nodejs /app/tsconfig.json ./

RUN npm ci --only=production && \
    npm install --save-dev typescript && \
    chown -R nextjs:nodejs /app

# Switch to non-root user
USER nextjs

EXPOSE 3000

CMD ["npm", "start"]
