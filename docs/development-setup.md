# AccountingAgents — Development Setup

## Prerequisites

- Python 3.11+
- Homebrew (macOS)
- Git
- ngrok account (free) — https://ngrok.com

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/pdesrochers01/accounting-agents.git
cd accounting-agents

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
```

Edit `.env`:
```
HITL_WEBHOOK_BASE_URL=https://your-ngrok-url.ngrok-free.app
HITL_NOTIFY_EMAIL=you@example.com
HITL_MODE=mock
```

## Running Tests

```bash
# All tests
PYTHONPATH=. .venv/bin/python tests/test_ingestion.py
PYTHONPATH=. .venv/bin/python tests/test_reconciliation.py
PYTHONPATH=. .venv/bin/python tests/test_hitl.py
PYTHONPATH=. .venv/bin/python tests/test_end_to_end_real.py
```

Expected results:
- `test_ingestion.py` — 9/9 passed
- `test_reconciliation.py` — 2/2 passed
- `test_hitl.py` — full HITL cycle passed
- `test_end_to_end_real.py` — 3/3 passed

## Running the HITL Demo

### Step 1 — Install and configure ngrok

```bash
brew install ngrok/ngrok/ngrok
ngrok config add-authtoken <your-token>
```

On macOS, remove Gatekeeper quarantine if needed:
```bash
xattr -d com.apple.quarantine /opt/homebrew/Caskroom/ngrok/3.38.0/ngrok
```

### Step 2 — Terminal 1: Flask webhook server

```bash
source .venv/bin/activate
PYTHONPATH=. python accounting_agents/webhook.py
# Running on http://127.0.0.1:5001
```

Note: macOS AirPlay Receiver occupies port 5000.
AccountingAgents uses port 5001 by default.
To disable AirPlay Receiver: System Settings → General →
AirDrop & Handoff → disable AirPlay Receiver.

### Step 3 — Terminal 2: ngrok tunnel

```bash
ngrok http 5001
# Copy the Forwarding URL: https://xxxx.ngrok-free.app
```

Update `.env`:
```
HITL_WEBHOOK_BASE_URL=https://xxxx.ngrok-free.app
```

### Step 4 — Terminal 3: Demo script

```bash
PYTHONPATH=. .venv/bin/python scripts/demo_hitl.py
```

Open the APPROVE / MODIFY / BLOCK link from any device.
Click "Visit Site" on the ngrok browser warning (free plan, once only).

## Project Conventions

- Always use `.venv/bin/python` in scripts (never bare `python`)
- Each agent node returns a **delta only** — never the full state
- `routing_signal` drives all conditional edges
- All code and comments in **English**
- Tests after every new file

## Claude Code Context

This project uses `CLAUDE.md` at the root as persistent context
for Claude Code sessions. Always start a new session by reading
CLAUDE.md before making changes.

## Adding a New Agent

1. Create `accounting_agents/nodes/your_agent.py`
2. Add routing logic to `accounting_agents/routing.py`
3. Register node and edges in `accounting_agents/graph.py`
4. Add fields to `accounting_agents/state.py` if needed
5. Write tests in `tests/test_your_agent.py`
6. Update `docs/use-cases/` with the new UC
7. Update `CLAUDE.md` progress section
