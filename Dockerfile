#SPDX-License-Identifier: AGPL-3.0-or-later

FROM debian:stable

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get -y update && \
    apt-get -y --no-install-recommends install python3 python3-pip python3-venv sudo git wget python3-setuptools xz-utils && \
    wget -q -O /tmp/upx.tar.xz "https://github.com/upx/upx/releases/download/v4.0.2/upx-4.0.2-amd64_linux.tar.xz" && \
    tar -xf /tmp/upx.tar.xz -C /tmp && \
    cp /tmp/upx-*/upx /usr/local/bin/ && \
    chmod +x /usr/local/bin/upx && \
    rm -rf /tmp/upx* && \
    wget "https://dl.google.com/go/go1.13.8.linux-amd64.tar.gz" -O "/tmp/go-linux-amd64.tar.gz" && \
    tar -C /usr/local -xf "/tmp/go-linux-amd64.tar.gz" && \
    rm "/tmp/go-linux-amd64.tar.gz"

RUN useradd -ms /bin/bash app &&\
    mkdir -p /home/app/venv &&\
    chown -R app:app /home/app &&\
    mkdir /var/log/app && chown app:app /var/log/app &&\
    sudo -u app bash -c "export GO111MODULE=on && /usr/local/go/bin/go get -d github.com/cheggaaa/pb/v3" &&\
    sudo -u app bash -c "export GO111MODULE=on && /usr/local/go/bin/go get -d golang.org/x/crypto/pbkdf2"
    

COPY --chown=app:app requirements.txt /home/app/

RUN ["sudo", "-u", "app", "/bin/bash", "-c", "python3 -m venv ~/venv/main && \
    ~/venv/main/bin/pip install -r ~/requirements.txt"]

COPY --chown=app:app app.py run.py run.sh /home/app/
COPY static /home/app/static
COPY templates /home/app/templates


EXPOSE 5000
CMD ["/usr/bin/sudo", "-u", "app", "/bin/bash", "/home/app/run.sh"]
