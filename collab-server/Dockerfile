FROM node:20-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund
COPY server.js ./
# LevelDB persistence lives here; mount a volume for durability if the host supports it.
ENV PERSIST_DIR=/data/y-leveldb
EXPOSE 1234
CMD ["node", "server.js"]
