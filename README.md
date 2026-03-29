# unforget-embed

Zero-config embedded Unforget memory server. PostgreSQL + pgvector + Unforget API — no Docker, no setup, one command.

## Install

```bash
pip install unforget-embed
```

## Usage

```bash
# Start the server (background daemon)
unforget-embed start

# Check status
unforget-embed status

# Stop
unforget-embed stop
```

Server runs on `http://127.0.0.1:9077` with the full Unforget API.

Data persists in `~/.unforget/data/`.

## How It Works

1. Starts an embedded PostgreSQL instance via `pgserver` (no Docker needed)
2. Enables the pgvector extension
3. Runs the Unforget FastAPI server on localhost
4. All data stored locally in `~/.unforget/data/`

No API keys. No external services. No configuration.

## Options

```bash
unforget-embed start --port 9077        # custom port
unforget-embed start --data-dir /path   # custom data directory
unforget-embed start --foreground       # run in foreground (don't daemonize)
```

## API

Once running, the full Unforget REST API is available:

```bash
# Write a memory
curl -X POST http://localhost:9077/v1/memory/write \
  -H "Content-Type: application/json" \
  -d '{"content": "User prefers dark mode", "org_id": "demo", "agent_id": "bot"}'

# Recall memories
curl -X POST http://localhost:9077/v1/memory/recall \
  -H "Content-Type: application/json" \
  -d '{"query": "user preferences", "org_id": "demo", "agent_id": "bot"}'
```

## License

Apache 2.0
