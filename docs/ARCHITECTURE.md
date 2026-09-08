# Architecture

Mic -> STT (faster-whisper) -> LLM Intent Parser -> Command Router -> Platform Adapter -> OS Action

The LLM never executes anything directly. It returns a structured command
chosen from the whitelist in `app/intent/schema.py`. The router in
`app/router/dispatcher.py` validates that command before dispatching it to
the correct platform adapter in `app/automation/`.

Full write-up with diagram: see the project design doc shared with the team.
