# Running the RAGAS demo

Set `ANTHROPIC_API_KEY` in the shell where the live demo will run. Run these
commands from the repository checkout:

Copy only the commands inside the code blocks, not the surrounding Markdown
fences or explanatory text.

```bash
cd "$(git rev-parse --show-toplevel)"
python3 -m venv .venv-ragas
.venv-ragas/bin/pip install -r requirements-ragas.txt

.venv-ragas/bin/python evaluations/faithfulness/ragas/ragas_faithfulness.py
```

If a different venv (e.g. `.venv-deepeval`) is already active in this shell, run `deactivate` first, or you'll get a `ModuleNotFoundError`.

`langchain-community` is pinned to `0.3.31` (not the latest 0.4.x) — ragas
0.4.3 imports `langchain_community.chat_models.vertexai` directly, and that
module was removed in the 0.4.x line as part of the package's
"sunset"/deprecation, causing `ModuleNotFoundError`. Reinstall from
`requirements-ragas.txt` if the environment becomes inconsistent.

Expected: GROUNDED ~1.0; HALLUCINATED ~0.333 (one of three claims grounded).

Notes:
- Uses `single_turn_ascore` per sample to avoid the `evaluate()` batch-runner
  hang seen in ragas 0.4.x.
- RAGAS defaults to OpenAI; we wrap `ChatAnthropic` in `LangchainLLMWrapper` to
  use Claude. Deprecation warnings about `LangchainLLMWrapper` and the metric
  import are harmless on 0.4.x.
- Keep RAGAS in its OWN venv — its `langchain-anthropic` dep upgrades `click`
  past what deepeval allows.

To run DeepEval and RAGAS together with normalized output, use the shared
runner after creating both environments:

```bash
cd "$(git rev-parse --show-toplevel)"
python3 tools/run_evals.py \
  --deepeval-python .venv-deepeval/bin/python \
  --ragas-python .venv-ragas/bin/python
```
