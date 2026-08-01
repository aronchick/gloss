ARG SOURCE_DATE_EPOCH=1735689600

FROM ghcr.io/astral-sh/uv:0.8.4@sha256:46968e602e1de60a6511cb090ba3945ea8fd9c2e3e321a66111b01baf0cb5ff8 AS uv
FROM ubuntu:22.04@sha256:0d779ea97881505f5ef0039336ee85edba27519bdba968c284c86ee066a973c8

ARG SOURCE_DATE_EPOCH

COPY --from=uv /uv /uvx /bin/

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8
ENV TZ=UTC
ENV UV_PYTHON_INSTALL_DIR=/opt/gloss/python
ENV UV_PROJECT_ENVIRONMENT=/opt/gloss/venv
ENV PATH=/opt/gloss/venv/bin:$PATH

# Bootstrap the CA bundle from checksum-pinned snapshot packages, then use one
# immutable Ubuntu snapshot for every APT input. The base image already pins
# libssl3, so only openssl and ca-certificates are needed for HTTPS bootstrap.
ADD --checksum=sha256:8bc80baf8b4a00ed111da33870a958ac9c8a64cb846471381dcc56486747bbec \
    https://snapshot.ubuntu.com/ubuntu/20260401T000000Z/pool/main/o/openssl/openssl_3.0.2-0ubuntu1.21_amd64.deb /tmp/openssl.deb
ADD --checksum=sha256:7b6d6a66bc70a0c0e87893cbe3d0db28e909710ea2f7c6be4d2b74806b1eef75 \
    https://snapshot.ubuntu.com/ubuntu/20260401T000000Z/pool/main/c/ca-certificates/ca-certificates_20240203~22.04.1_all.deb /tmp/ca-certificates.deb

RUN dpkg -i /tmp/openssl.deb /tmp/ca-certificates.deb \
    && rm /tmp/openssl.deb /tmp/ca-certificates.deb \
    && sed -i \
      -e 's|http://archive.ubuntu.com/ubuntu/|https://snapshot.ubuntu.com/ubuntu/20260401T000000Z/|g' \
      -e 's|http://security.ubuntu.com/ubuntu/|https://snapshot.ubuntu.com/ubuntu/20260401T000000Z/|g' \
      /etc/apt/sources.list \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install -y --no-install-recommends \
      libreoffice-impress=1:7.3.7-0ubuntu0.22.04.10 \
      libreoffice-core=1:7.3.7-0ubuntu0.22.04.10 \
      poppler-utils=22.02.0-2ubuntu0.12 \
      locales=2.35-0ubuntu3.13 \
      libfaketime=0.9.8-9 \
      fontconfig=2.13.1-4.2ubuntu5 \
    && test "$(dpkg-query -W -f='${Version}' libreoffice-impress)" = '1:7.3.7-0ubuntu0.22.04.10' \
    && test "$(dpkg-query -W -f='${Version}' libreoffice-core)" = '1:7.3.7-0ubuntu0.22.04.10' \
    && test "$(dpkg-query -W -f='${Version}' poppler-utils)" = '22.02.0-2ubuntu0.12' \
    && test "$(dpkg-query -W -f='${Version}' libfaketime)" = '0.9.8-9' \
    && locale-gen en_US.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY grader/ /opt/gloss/grader/
COPY benchmark/ /opt/gloss/benchmark/
COPY schemas/ /opt/gloss/schemas/
COPY Dockerfile /opt/gloss/build/Dockerfile

# Fontconfig intentionally sees only the 26 content-addressed files in the
# benchmark manifest, even if LibreOffice dependencies ship additional fonts.
RUN install -d /opt/gloss/fontconfig/cache \
    && printf '%s\n' \
      '<?xml version="1.0"?>' \
      '<!DOCTYPE fontconfig SYSTEM "fonts.dtd">' \
      '<fontconfig>' \
      '  <dir>/opt/gloss/benchmark/fonts/files</dir>' \
      '  <cachedir>/opt/gloss/fontconfig/cache</cachedir>' \
      '  <config><rescan><int>0</int></rescan></config>' \
      '</fontconfig>' \
      > /opt/gloss/fontconfig/fonts.conf

ENV FONTCONFIG_FILE=/opt/gloss/fontconfig/fonts.conf
ENV FONTCONFIG_PATH=/opt/gloss/fontconfig

# Freeze wall-clock inputs for LibreOffice and every grader subprocess without
# corrupting timeout/elapsed-time measurements based on monotonic clocks. Apply
# this before building the grader so the installed local project is also
# consistent with the canonical clock under `uv sync --check`.
ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1
ENV FAKETIME="@2025-01-01 00:00:00"
ENV FAKETIME_DONT_FAKE_MONOTONIC=1
ENV FAKETIME_NO_CACHE=1
ENV SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH}
ENV PYTHONDONTWRITEBYTECODE=1

# Install the exact locked Python graph and the grader itself.
RUN uv python install 3.12.11 \
    && uv venv --python 3.12.11 /opt/gloss/venv \
    && uv sync --frozen --no-dev --no-editable --project /opt/gloss/grader \
    && fc-cache -f

RUN /opt/gloss/venv/bin/python - <<'PY'
import hashlib
import json
import subprocess
from pathlib import Path

font_root = Path("/opt/gloss/benchmark/fonts")
manifest = json.loads((font_root / "manifest.json").read_text(encoding="utf-8"))
expected = {
    str((font_root / entry["local_path"]).resolve()): entry["sha256"]
    for entry in manifest["files"]
}
actual = set(
    subprocess.check_output(["fc-list", "-f", "%{file}\\n"], text=True).splitlines()
)
if actual != set(expected):
    raise SystemExit(
        f"Fontconfig inventory mismatch: missing={sorted(set(expected) - actual)} "
        f"extra={sorted(actual - set(expected))}"
    )
for path, expected_sha256 in expected.items():
    actual_sha256 = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if actual_sha256 != expected_sha256:
        raise SystemExit(f"Font hash mismatch: {path}")
PY

# Fixed non-root identity for the hosted runner contract.
RUN groupadd --gid 10001 grader \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin grader
USER 10001:10001
WORKDIR /workspace

ENTRYPOINT ["gloss"]
