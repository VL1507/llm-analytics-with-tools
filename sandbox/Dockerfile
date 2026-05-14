FROM python:3.13-slim

RUN apt-get update \ 
    && apt-get install -y --no-install-recommends libfreetype6 libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /sandbox/input /sandbox/output && chmod -R 777 /sandbox

WORKDIR /sandbox
