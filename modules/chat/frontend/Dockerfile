FROM node:22-alpine AS livekit-sdk
WORKDIR /sdk
RUN TARBALL="$(npm pack --silent livekit-client@2.22.3)" \
    && test -n "$TARBALL" \
    && tar -xzf "$TARBALL" \
    && test -f /sdk/package/dist/livekit-client.umd.js

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY app.js /usr/share/nginx/html/app.js
COPY ptt.js ptt-history.js /usr/share/nginx/html/
COPY crisis.js crisis.css crisis-media.js /usr/share/nginx/html/
COPY styles.css /usr/share/nginx/html/styles.css
COPY feature-policy.js /usr/share/nginx/html/feature-policy.js
COPY ptt-composer-layout.js /usr/share/nginx/html/ptt-composer-layout.js
COPY --from=livekit-sdk /sdk/package/dist/livekit-client.umd.js /usr/share/nginx/html/livekit-client.umd.js