FROM nginx:1.27-alpine

RUN apk add --no-cache wget

COPY docker-entrypoint.sh /custom-entrypoint.sh
RUN sed -i 's/\r$//' /custom-entrypoint.sh && chmod +x /custom-entrypoint.sh

COPY dia.ebl-bd.com.conf /etc/nginx/conf.d/default.conf

ENTRYPOINT ["/custom-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
