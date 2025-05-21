FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.4.28 /uv /uvx /bin/
WORKDIR /app
COPY . .
RUN uv sync --frozen
ENTRYPOINT ["uv", "run"]
CMD ["python", "-m", "contestdojo_verifier_bot"]
