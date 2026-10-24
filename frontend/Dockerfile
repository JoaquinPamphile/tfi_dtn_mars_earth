# Shell de desarrollo del Laboratorio DTN.
# No forma parte de la release científica.
# No copia evidence/ dentro de la imagen: compose la monta en solo lectura.
FROM node:22-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
