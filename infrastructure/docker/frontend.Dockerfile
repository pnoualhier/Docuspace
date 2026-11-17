# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=${VITE_API_URL}

COPY package.json ./
COPY package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install --no-audit --no-fund; fi

COPY . .
RUN npm run build

# Stage 2: Serve with lightweight unprivileged Nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY infrastructure/nginx/frontend.conf /etc/nginx/conf.d/default.conf

RUN sed -i 's|/run/nginx.pid|/tmp/nginx.pid|g' /etc/nginx/nginx.conf \
    && sed -i '/^user /d' /etc/nginx/nginx.conf \
    && chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx/conf.d

EXPOSE 3000

USER nginx

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:3000/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
