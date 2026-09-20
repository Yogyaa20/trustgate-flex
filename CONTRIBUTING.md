# Contributing

This is a hackathon prototype. Contributions are welcome after the BuildForge Hackathon concludes.

## Development Setup

```bash
git clone https://github.com/Yogyaa20/trustgate-flex
cd trustgate-flex
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/seed_db.py
```

## Running Tests

```bash
pytest tests/ -v
```

All 23+ tests must pass before submitting a pull request.

## Code Style

- Python: follow PEP 8
- No magic numbers — all risk weights must be named constants
- All new API endpoints must have try/except with structured error responses
- All new risk factors must have a corresponding pytest test

## Adding a New Risk Factor

1. Add the factor logic to `backend/services/risk_engine.py`
2. Add it to the `evaluate()` function's factor list
3. Document the weight and direction in `ARCHITECTURE.md`
4. Add at least 2 pytest tests in `tests/test_services/test_risk_engine.py`
5. Update the factor table in `README.md`

## Adding a New Policy Rule

1. Add the rule to `backend/services/policy_engine.py`
2. Ensure it is evaluated in the correct priority order
3. Add a pytest test for the new rule
4. Document it in `ARCHITECTURE.md` under the policy chain section

## What NOT to Add

- No ML models without a labelled dataset and formal evaluation plan
- No time-of-day as a risk signal (this is a fairness constraint, not a bug)
- No surveillance features (keystroke logging, screen capture, etc.)
- No hardcoded credentials

## Pull Request Checklist

- [ ] Tests pass (`pytest tests/ -v`)
- [ ] No new sensitive data in DB files (`.db` files are gitignored)
- [ ] `.env` not committed
- [ ] LIMITATIONS.md updated if a known limitation is added or removed
- [ ] No time-of-day signal introduced

## Reporting Issues

Use [GitHub Issues](https://github.com/Yogyaa20/trustgate-flex/issues).
Include: what you expected, what happened, steps to reproduce.
