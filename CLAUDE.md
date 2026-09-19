# Atlas: responsible use of Nebius Token Factory

This project runs on limited Nebius Token Factory credits. Follow these
rules on any change or test:

- Never read, print, paste, or upload `NEBIUS_API_KEY`; it can only live
  in the local `.env` file or the deployment's secret manager.
- Don't make external calls to the model unless they're needed for the
  current task. To check connectivity, use only `python -m core.llm`: it
  runs one call to Nemotron Nano with output capped at four tokens.
- Don't use Nemotron Ultra for connectivity checks, debugging, or
  examples. Before a test with Ultra, ingestion, batch evaluation,
  fine-tuning, sandbox, or deployment that spends Nebius credits, explain
  the purpose, estimate the consumption, and ask for explicit
  confirmation.
- Default to mocks, fixtures, and local tests. Integration tests against
  Token Factory should be small, deliberate, and report the tokens
  consumed, without logging sensitive prompts.
- Keep every call to Token Factory inside `core/llm.py`; don't duplicate
  the API URL or create direct clients in other modules.
