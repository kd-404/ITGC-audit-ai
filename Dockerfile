# ITGC Continuous Audit Platform - container image for Hugging Face Spaces
# (Docker SDK) or any other container host (Render, Fly.io, plain `docker run`).
#
# This packages the webapp exactly as it runs locally; it does not add a
# database, auth, or multi-tenancy - see the "Architecture Guidebook" doc for
# what a real production deployment (as opposed to a public demo) still needs.

FROM python:3.11-slim

# reportlab/openpyxl need no system packages beyond the base image; keep the
# image lean rather than installing a compiler toolchain we don't need.
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build the bundled ACME sample dataset into the image so a fresh demo
# instance has something to load immediately ("Load sample" in the UI works
# out of the box, with no click-through setup step for a visitor).
RUN python3 scripts/generate_dataset.py && \
    python3 scripts/generate_hard_scenario.py && \
    python3 scripts/generate_hard_scenario_solstice.py && \
    python3 scripts/generate_hard_scenario_harborview.py

# Hugging Face Spaces (Docker SDK) injects PORT=7860 and expects the app to
# bind 0.0.0.0 - webapp/server.py already detects this via the PORT env var.
ENV PORT=7860
EXPOSE 7860

# A container's filesystem is writable but ephemeral (rebuilds/restarts wipe
# it) - fine for a public demo instance where every visitor sees the same
# fresh state; not a substitute for real persistence in production.
CMD ["python3", "webapp/server.py"]
