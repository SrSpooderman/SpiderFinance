FROM node:22-alpine AS build
WORKDIR /app
ARG VITE_BASE_PATH=/
ENV VITE_BASE_PATH=$VITE_BASE_PATH
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
ENV API_UPSTREAM=http://backend:8000 APP_BASE_PATH=/
ENV NGINX_ENVSUBST_TEMPLATE_DIR=/etc/nginx/templates/public
COPY nginx.conf.template /etc/nginx/templates/public/default.conf.template
COPY nginx.admin.conf.template /etc/nginx/templates/admin/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
