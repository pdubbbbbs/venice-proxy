# Contributing

Bug reports and pull requests welcome.

## Reporting issues

Open an issue on GitHub. Include:
- Your OS and Python version
- The error message or unexpected behaviour
- Steps to reproduce

## Pull requests

1. Fork the repo
2. Create a branch (`git checkout -b my-fix`)
3. Make your changes
4. Test with `python3 -m pytest tests/` (or manually with `curl`)
5. Submit a PR with a clear description

## Code style

- Python: PEP 8, type hints where practical, functions under 50 lines
- Keep the router logic in `router/app.py` — no additional dependencies beyond `requirements.txt`
