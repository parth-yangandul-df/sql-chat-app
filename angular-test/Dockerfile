FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 4200
CMD ["npx", "@angular/cli@21", "serve", "--port", "4200", "--host", "0.0.0.0"]
