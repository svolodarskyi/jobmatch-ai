FROM node:20-slim

WORKDIR /app

# Copy only the package manifests so this layer is cached unless dependencies change.
# Source code is bind-mounted at runtime — no COPY . . here.
COPY package.json package-lock.json ./

RUN npm install

# node_modules lives inside the image layer; the docker-compose anonymous
# volume at /app/node_modules shields it from being overwritten by the
# host bind-mount of the source tree.
CMD ["npm", "run", "dev", "--", "--host"]
