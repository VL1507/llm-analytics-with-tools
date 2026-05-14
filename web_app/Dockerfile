
FROM docker:29.4.3-cli AS docker-cli

FROM python:3.13-slim


COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

RUN apt-get update \
   && rm -rf /var/lib/apt/lists/* \
   && apt-get clean

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
   && pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
