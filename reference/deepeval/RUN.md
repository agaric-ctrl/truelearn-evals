# Running the DeepEval demo

Set `ANTHROPIC_API_KEY` in the shell where the live demo will run. Run these
commands from the repository checkout:

Copy only the commands inside the code blocks, not the surrounding Markdown
fences or explanatory text.

```bash
cd "$(git rev-parse --show-toplevel)"
python3 -m venv .venv-deepeval
.venv-deepeval/bin/pip install -r requirements-deepeval.txt

.venv-deepeval/bin/python reference/deepeval/faithfulness_demo.py
```

If a different venv (e.g. `.venv-ragas`) is already active in this shell, run `deactivate` first, or you'll get `ModuleNotFoundError: No module named 'deepeval'`.

Expected: GROUNDED scores 1.0 and passes; HALLUCINATED scores ~0.5 and fails
(one of two claims grounded). The metric is an LLM call — DeepEval defaults to
OpenAI, so we pass `model=AnthropicModel(...)` to use Claude as the judge.

Uses `.measure()` directly (not `assert_test`) so both cases run and print
instead of pytest aborting on the first failure.

To run DeepEval and RAGAS together with normalized output, use the shared
runner after creating both environments:

```bash
cd "$(git rev-parse --show-toplevel)"
python3 tools/run_evals.py \
  --deepeval-python .venv-deepeval/bin/python \
  --ragas-python .venv-ragas/bin/python
```
