FROM python:3.12-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends git texlive-full poppler-utils \
    && apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.4.28 /uv /uvx /bin/
WORKDIR /app
COPY . .
RUN uv sync --frozen
ENTRYPOINT ["uv", "run"]
CMD ["python", "-m", "bmt_discord_bot"]
