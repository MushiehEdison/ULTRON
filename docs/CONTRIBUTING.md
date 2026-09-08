# Contributing

## Branches
- `main` — always working
- `feature/<module>-<short-desc>` e.g. `feature/stt-mic-capture`

## Workflow
1. Branch off `main`
2. Build against the interface in `app/automation/base.py` (or the relevant
   module contract) — don't change shared interfaces without flagging it
3. Open a PR into `main`
4. One review + green CI before merge

## Module ownership
See project board / task assignments. Each module folder under `app/` has
one owner during Week 2.
