# SystemDesigner voice interviewer — same code as the local CLI, packaged as a
# small service. Keys are injected via environment variables (see .env.example).
#
#   docker build -t systemdesigner-interviewer .
#   docker run --rm --env-file .env systemdesigner-interviewer \
#       --join "+15551234567,,123456789#" --out /portfolios/my-system
#
# Mount a volume at /app/portfolios to keep the generated portfolio and the
# resumable state file outside the container.
FROM python:3.12-slim

WORKDIR /app

# Build deps first for layer caching.
COPY pyproject.toml ./
COPY voice_interview ./voice_interview
RUN pip install --no-cache-dir -e ".[voice]"

# The protocol files are data the interviewer reads at runtime.
COPY templates ./templates
COPY interview-protocol ./interview-protocol
COPY scripts ./scripts

VOLUME ["/app/portfolios"]

ENTRYPOINT ["python", "scripts/run_interview.py"]
CMD ["--help"]
