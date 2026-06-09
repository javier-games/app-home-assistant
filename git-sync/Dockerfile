ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1

# Runtime dependencies:
#  - git / openssh-client : the actual sync engine
#  - inotify-tools        : efficient local change detection (inotifywait)
#  - python3              : orchestrator, scheduler and ingress web UI
RUN apk add --no-cache \
    git \
    openssh-client \
    inotify-tools \
    python3 \
    tzdata

# Copy add-on files (run.sh + python app) into the image.
COPY rootfs /
RUN chmod a+x /run.sh

WORKDIR /app
CMD [ "/run.sh" ]
