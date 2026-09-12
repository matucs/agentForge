FROM python:3.11-slim

# The Developer/Reviewer agents shell out to the real `git` CLI
# (app/git_integration/git_ops.py) — required in the image, not just on the
# host running tests.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .
RUN pip install --no-cache-dir -e ".[dev]"
RUN git config --global user.email "agentforge@example.com" \
    && git config --global user.name "AgentForge"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
