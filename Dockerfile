# syntax=docker/dockerfile:1
#
# ParSub REST API
#
#   docker build -t parsub-api .
#   docker run -p 8000:8000 -v parsub-data:/data parsub-api
#
# Open http://localhost:8000/ for the interactive API documentation.
# Generated code, plots and data are stored in /data (PARSUB_OUTPUT_ROOT).

# Official Python image; override with --build-arg BASE_IMAGE=... to use a mirror
ARG BASE_IMAGE=python:3.12-slim

# ---- build the wheel ---------------------------------------------------------
FROM ${BASE_IMAGE} AS build
WORKDIR /src
COPY pyproject.toml README.md LICENSE MANIFEST.in ./
COPY src ./src
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels .

# ---- runtime image -----------------------------------------------------------
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="ParSub REST API" \
      org.opencontainers.image.description="Turn the mathematics in LaTeX documents into runnable Python computations, plots and data" \
      org.opencontainers.image.source="https://github.com/PSubrat29/parsub" \
      org.opencontainers.image.url="https://psubrat29.github.io/parsub/" \
      org.opencontainers.image.documentation="https://psubrat29.github.io/parsub/docs/user_guide.html#docker" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    PARSUB_API_HOST=0.0.0.0 \
    PARSUB_API_PORT=8000 \
    PARSUB_OUTPUT_ROOT=/data

COPY --from=build /wheels /wheels
RUN pip install /wheels/*.whl \
    && rm -rf /wheels \
    && useradd --create-home --uid 1000 --shell /usr/sbin/nologin parsub \
    && mkdir -p /data \
    && chown parsub:parsub /data

USER parsub
WORKDIR /home/parsub
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request as u; u.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PARSUB_API_PORT', '8000'), timeout=4)"

CMD ["parsub-api"]
