FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8
ENV TZ=UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-impress libreoffice-core \
    fonts-liberation fonts-noto fonts-noto-cjk \
    fonts-crosextra-carlito fonts-crosextra-caladea \
    python3 python3-pip python3-venv \
    locales \
    && locale-gen en_US.UTF-8 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Font policy: ONLY the packages above are installed.
# Carlito = metric-compatible Calibri; Caladea = metric-compatible Cambria.
# No system default fonts beyond what these packages pull in.

# Install grader package
COPY grader/ /opt/acidslide/grader/
WORKDIR /opt/acidslide/grader
RUN python3 -m pip install --no-cache-dir -e .

# Copy benchmark data and schemas
COPY benchmark/ /opt/acidslide/benchmark/
COPY schemas/ /opt/acidslide/schemas/

# Non-root user for security
RUN useradd -m -s /bin/bash grader
USER grader
WORKDIR /workspace

ENTRYPOINT ["acidslide"]
