FROM docker.io/python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY config/filters.json ./config/filters.json
COPY src/ ./src
COPY data/fixtures/ ./data/fixtures
COPY voice_cleaner.py ./
CMD ["/bin/bash"]
