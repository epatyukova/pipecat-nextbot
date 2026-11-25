## Summary

<!-- What changed, and why is this the right scope? -->

## Validation

<!-- List the commands or manual checks actually performed. -->

- [ ] `uv run ruff check .`
- [ ] `uv run ruff format --check .`
- [ ] `uv run mypy .` (when Python source exists)
- [ ] `uv run pytest` (when tests exist)

## Risk and rollout

<!-- Note compatibility, migration, security, performance, or deployment concerns. Use “None” when not applicable. -->

## Checklist

- [ ] The change is focused and does not include unrelated cleanup.
- [ ] Tests cover changed behaviour, or the reason they do not is documented.
- [ ] Documentation and examples are updated where needed.
- [ ] No secrets, credentials, or private data are included.
- [ ] Breaking changes and follow-up work are clearly identified.
