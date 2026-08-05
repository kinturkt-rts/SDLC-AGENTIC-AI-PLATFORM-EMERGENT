#!/bin/sh
# Render nginx config from APP_NAME / UI_PORT, then start nginx.
set -eu

APP_NAME="${APP_NAME:?APP_NAME is required}"
UI_PORT="${UI_PORT:-8501}"

export APP_NAME UI_PORT
envsubst '${APP_NAME} ${UI_PORT}' \
  < /etc/nginx/templates/nginx.react.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
