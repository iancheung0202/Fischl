FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# libfribidi lets Pillow shape text, as it did before Docker; procps gives pkill.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libfribidi0 procps \
    && rm -rf /var/lib/apt/lists/*

# The lock file lists every package at the version production ran before Docker.
COPY requirements.lock /tmp/
RUN pip install --no-cache-dir --no-deps -r /tmp/requirements.lock

WORKDIR /srv/Fischl
CMD ["bash", "start.sh"]
