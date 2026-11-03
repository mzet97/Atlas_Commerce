# postgres + Atlas bootstrap baked in: bind mounts of repo dirs break on
# SELinux hosts and non-POSIX filesystems, so the initdb scripts travel
# with the image. Migration dirs come in via additional_contexts.
FROM postgres:17
COPY initdb/ /docker-entrypoint-initdb.d/
COPY --from=control_migrations . /docker-entrypoint-initdb.d/50-control-migrations/
COPY --from=catalog_migrations . /docker-entrypoint-initdb.d/60-service-migrations/catalog/
COPY --from=offers_migrations . /docker-entrypoint-initdb.d/60-service-migrations/offers/
COPY --from=inventory_migrations . /docker-entrypoint-initdb.d/60-service-migrations/inventory/
COPY --from=payment_migrations . /docker-entrypoint-initdb.d/60-service-migrations/payment/
COPY --from=order_migrations . /docker-entrypoint-initdb.d/60-service-migrations/order/
