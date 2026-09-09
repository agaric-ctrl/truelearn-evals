# Running the Promptfoo configs

Promptfoo is a Node tool. Use Node 24 and set `ANTHROPIC_API_KEY` only in the
shell where live generator evaluations will run.

Copy only the commands inside the code blocks, not the surrounding Markdown
fences or explanatory text.

```bash
nvm use 24
cd "$(git rev-parse --show-toplevel)/evaluations/faithfulness/promptfoo"
```

Run the two-case judge test:

```bash
npx promptfoo@latest eval -c 01_faithfulness_pass_fail.yaml --no-cache
npx promptfoo@latest view
```

Run the 30-case judge-validation suite:

```bash
npx promptfoo@latest eval -c 02_faithfulness_suite_20.yaml --no-cache
npx promptfoo@latest view
```

Run the live generator test:

```bash
npx promptfoo@latest eval -c 03_generator_test.yaml --no-cache
npx promptfoo@latest view
```

Run the enriched-source controlled experiment:

```bash
npx promptfoo@latest eval -c 04_generator_enriched.yaml --no-cache
npx promptfoo@latest view
```

Notes:
- `echo` provider (01, 02) returns the answer text verbatim so only the judge
  makes model calls. This isolates the scorer.
- Generator providers use the full `anthropic:messages:<model>` id with a
  `config:` block. The bare-string form triggered a "Converting circular
  structure to JSON" serialization bug when the provider had to GENERATE.
- `temperature` is deprecated on Sonnet 5 / Opus 4.x and is silently omitted.
  Harmless.
- The two judge-validation configs use the `echo` provider and do not require
  an API key. The generator configs make live provider calls and do require
  `ANTHROPIC_API_KEY`.
- Promptfoo can return exit code `100` when expected adversarial assertions
  fail. Treat that as an evaluation result, not automatically as an
  infrastructure error.

From anywhere inside the repository checkout, normalize the latest Promptfoo
JSON output for comparison:

```bash
cd "$(git rev-parse --show-toplevel)/evaluations/faithfulness/promptfoo"
python3 ../../../tools/promptfoo_results.py \
  .promptfoo/output.json \
  ../../../results/promptfoo-results.json
```
