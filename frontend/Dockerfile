FROM nginx:1.27-alpine
COPY care.conf /etc/nginx/conf.d/default.conf
COPY index.html care.css shift-workspace.css /usr/share/nginx/html/
COPY src /usr/share/nginx/html/src
