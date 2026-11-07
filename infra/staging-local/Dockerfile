# TEMPORARY local "staging host" (S-01-T12) until the real staging VM exists (S-02).
# Docker-in-Docker with sshd: behaves like a small Linux VM with Docker, reachable over SSH as the
# non-root `deploy` user with key-only authentication. Run with --privileged (see up.sh).
FROM docker:29.9.3-dind

RUN apk add --no-cache openssh-server bash curl coreutils \
    && addgroup -S docker 2>/dev/null || true \
    && adduser -D -s /bin/bash -G docker deploy \
    && sed -i 's/^deploy:!:/deploy:*:/' /etc/shadow \
    && mkdir -p /srv/numo9 /home/deploy/.ssh \
    && chown -R deploy:docker /srv/numo9 /home/deploy/.ssh \
    && chmod 700 /home/deploy/.ssh

COPY sshd_config /etc/ssh/sshd_config
COPY entrypoint.sh /usr/local/bin/staging-host-entrypoint.sh
RUN chmod 755 /usr/local/bin/staging-host-entrypoint.sh

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/staging-host-entrypoint.sh"]
