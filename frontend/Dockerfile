# Shell de desarrollo del Laboratorio DTN.
# No forma parte de la release científica ni lee evidence/.
FROM node:22-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
