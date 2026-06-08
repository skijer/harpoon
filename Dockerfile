# syntax=docker/dockerfile:1
#
# Harpoon multiplayer server.
# Build:  docker build -t harpoon .
# Run:    docker run -d --name harpoon -p 8765:8765 --restart unless-stopped harpoon

FROM python:3.12-slim

# No .pyc files; unbuffered stdout so `docker logs` is live.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first — this layer is cached unless requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code.
COPY harpoon/ ./harpoon/
COPY server.py .

# Run unprivileged. The relay holds no state on disk, so read-only is fine.
RUN useradd --create-home --uid 10001 harpoon
USER harpoon

EXPOSE 8765

# Defaults can be overridden, e.g.  docker run harpoon --port 9000
ENTRYPOINT ["python", "server.py"]
CMD ["--host", "0.0.0.0", "--port", "8765"]
