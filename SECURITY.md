# Security Policy

MemoBox is currently an early-stage local-first project.

## Reporting a Vulnerability

Please open a private security advisory on GitHub if available, or create an issue with minimal reproduction details and avoid publishing secrets, tokens, or private traces.

## Data Handling Notes

- Raw traces may contain sensitive conversation or tool output.
- Do not commit `.memobox/` stores unless the data is intentionally public.
- Prefer redaction before sharing memory bodies or raw traces.
- Future versions should add first-class redaction and privacy policy hooks.

