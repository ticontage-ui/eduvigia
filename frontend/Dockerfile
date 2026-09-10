FROM node:22-alpine
WORKDIR /app

COPY .npmrc package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY vite.config.js index.html ./
COPY public ./public
COPY src ./src

RUN npm run build

EXPOSE 5173
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "5173"]
