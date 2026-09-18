FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY app.js /usr/share/nginx/html/app.js
COPY ptt.js ptt-history.js /usr/share/nginx/html/
COPY crisis.js crisis.css /usr/share/nginx/html/
COPY styles.css /usr/share/nginx/html/styles.css
# EduVigIA Chat product feature policy
COPY feature-policy.js /usr/share/nginx/html/feature-policy.js
# EduVigIA Chat PTT composer layout
COPY ptt-composer-layout.js /usr/share/nginx/html/ptt-composer-layout.js