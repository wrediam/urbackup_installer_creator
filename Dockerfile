#SPDX-License-Identifier: AGPL-3.0-or-later

FROM debian:stable

ENV DEBIAN_FRONTEND=noninteractive

# Update and install packages in separate steps
RUN apt-get -y update && \
    apt-get -y --no-install-recommends install \
    python3 \
    python3-pip \
    python3-venv \
    sudo \
    git \
    wget \
    python3-setuptools \
    ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python packages with --break-system-packages flag
RUN pip3 install --break-system-packages virtualenvwrapper

# Download and install Go
RUN wget "https://go.dev/dl/go1.20.5.linux-amd64.tar.gz" -O "/tmp/go-linux-amd64.tar.gz" && \
    tar -C /usr/local -xf "/tmp/go-linux-amd64.tar.gz" && \
    rm "/tmp/go-linux-amd64.tar.gz"

RUN useradd -ms /bin/bash app &&\
    echo "export WORKON_HOME=$HOME/.virtualenvs" >> /home/app/.bashrc &&\
    mkdir -p /home/app/.virtualenvs &&\
    echo "source /usr/local/bin/virtualenvwrapper_lazy.sh" >> /home/app/.bashrc &&\
    chown -R app:app /home/app &&\
    mkdir /var/log/app && chown app:app /var/log/app

# Set up Go module and install Go packages
RUN mkdir -p /home/app/gomod && \
    chown -R app:app /home/app && \
    echo 'export PATH=$PATH:/usr/local/go/bin:/home/app/go/bin' >> /home/app/.bashrc && \
    sudo -u app bash -c 'cd /home/app/gomod && /usr/local/go/bin/go mod init urbackup_installer' && \
    sudo -u app bash -c '/usr/local/go/bin/go install github.com/cheggaaa/pb/v3@latest' && \
    sudo -u app bash -c '/usr/local/go/bin/go install golang.org/x/crypto/pbkdf2@latest'
    

COPY --chown=app:app requirements.txt /home/app/

RUN ["sudo", "-u", "app", "/bin/bash", "-c", "export VIRTUALENVWRAPPER_PYTHON=python3 &&\
    . /usr/local/bin/virtualenvwrapper.sh &&\
    mkvirtualenv --python=/usr/bin/python3 main -r ~/requirements.txt"]

COPY --chown=app:app app.py run.py run.sh /home/app/
COPY static /home/app/static
COPY templates /home/app/templates


EXPOSE 5000
CMD ["/usr/bin/sudo", "-u", "app", "/bin/bash", "/home/app/run.sh"]
