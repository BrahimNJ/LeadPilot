# syntax=docker/dockerfile:1

# --- build: turn the project and its dependencies into wheels ---------------------------
FROM python:3.13-slim AS build
WORKDIR /src
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip wheel --no-cache-dir --wheel-dir /wheels .

# --- runtime: only the wheels, no compiler, no source tree, not root --------------------
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

RUN useradd --create-home --uid 10001 leadpilot
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

USER leadpilot
WORKDIR /home/leadpilot
EXPOSE 8080

# Cloud Run sets PORT; exec keeps uvicorn as PID 1 so it receives SIGTERM directly.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --proxy-headers
