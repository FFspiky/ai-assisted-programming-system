ARG PYTHON_IMAGE=python:3.11-slim-bookworm
FROM ${PYTHON_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends g++ \
    && rm -rf /var/lib/apt/lists/*
COPY run_submission.py /usr/local/bin/run_submission.py
USER 65534:65534
WORKDIR /work
ENTRYPOINT ["python3", "-I", "/usr/local/bin/run_submission.py"]
