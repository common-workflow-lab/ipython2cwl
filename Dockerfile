FROM python:3.6.11-slim-buster

RUN apt update && \
    apt install -y --no-install-recommends \
    git \
    tini && \
    apt clean &&\
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN pip install -U pip setuptools wheel && \
    python3 setup.py install

ENV UID=1000
RUN useradd -M -u ${UID} -U jupyter

USER jupyter

ENTRYPOINT ["tini", "--"]
CMD ["jupyter-repo2cwl"]
