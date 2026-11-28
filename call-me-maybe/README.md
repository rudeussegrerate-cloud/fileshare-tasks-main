*This project has been created as part of the 42 curriculum by tusandri.*

# call me maybe

## Description

`call-me-maybe` is a function-calling system for small language models. Given a
natural-language question such as *"What is the sum of 40 and 2?"*, it does not
answer the question. Instead, it produces the structured call that would solve
it:

```json
{
    "prompt": "What is the sum of 40 and 2?",
    "name": "fn_add_numbers",
    "parameters": {"a": 40, "b": 2}
}
```

The core of the project is **constrained decoding**: the 0.6B-parameter model
(`Qwen/Qwen3-0.6B`) never freely writes its answer. At every generation step the
decoder restricts the candidate tokens to those that keep the output a
schema-valid function call, so the produced JSON is valid **by construction** —
100% parseable, with argument types enforced by the schema in
`functions_definition.json`.

Note on this repository: it hosts several 42 projects side by side, so the
project root of *call-me-maybe* is the `call-me-maybe/` directory. Every
command below must be run from that directory.

## Instructions

### Prerequisites

- Python 3.10 or later
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- The provided `llm_sdk` package (already copied at the project root, next to `src/`)

### Installation

```bash
make install        # or simply: uv sync
```

The reviewer and the moulinette only need to run `uv sync`: the lockfile pins
every dependency (numpy, pydantic, and the torch/transformers/huggingface-hub
stack required by `llm_sdk`). The first run downloads the Qwen3-0.6B weights
from the Hugging Face hub and caches them.

### Run

```bash
make run
```

which executes:

```bash
uv run python -m src [--functions_definition <file>] [--input <file>] [--output <file>]
```

Defaults read `data/input/function_calling_tests.json` and
`data/input/functions_definition.json`, and write
`data/output/function_calling_results.json`.

### Example usage

```bash
uv run python -m src
uv run python -m src \
    --functions_definition data/input/functions_definition.json \
    --input data/input/function_calling_tests.json \
    --output data/output/function_calling_results.json
uv run python -m src --input my_prompts.json --output my_results.json
```

Input files:

- `functions_definition.json`: JSON array of available functions, each with a
  `name`, a `description`, typed `parameters` and a `returns` type
  (`number`, `integer`, `string`, `boolean`, `null`).
- `function_calling_tests.json`: JSON array of `{"prompt": "..."}` entries.

Output file: one JSON array where each entry contains exactly the keys
`prompt`, `name` and `parameters`.

### Makefile targets

| Target       | Effect                                                          |
| ------------ | --------------------------------------------------------------- |
| `make install` | Install/synchronise dependencies with uv                      |
| `make run`     | Run the program on the default files                           |
| `make debug`   | Run the program under `pdb`                                    |
| `make lint`    | `flake8 .` plus `mypy` with the flags required by the subject  |
| `make lint-strict` | Same lint with `mypy --strict`                            |
| `make test`    | Run the pytest suite                                           |
| `make clean`   | Remove caches (`__pycache__`, `.mypy_cache`, `.pytest_cache`)  |

## Algorithm explanation

### 1. Prompting (context only)

For each prompt the decoder builds a plain-completion prompt:

```text
Available functions:
- fn_add_numbers(a: number, b: number): Add two numbers together and return their sum.
- fn_greet(name: string): Generate a greeting message for a person by name.
Question: What is the sum of 40 and 2?
Function call: {"name": "
```

The prompt only gives the model context. The structure of the answer is never
left to the model: every syntactic fragment (`"`, `:`, `,`, `{`, `}`, key
names) is appended by the decoder itself, and the model is consulted only
where a genuine decision exists.

### 2. Vocabulary mapping

`Small_LLM_Model.get_path_to_vocab_file()` gives the model vocabulary: a JSON
map from token strings to ids. Qwen tokenizers are byte-level BPE: vocabulary
entries are written in a reversible unicode encoding of the raw bytes (a space
is `Ġ`, a newline is `Ċ`, `é` is the two characters `Ã©`...). `src/vocab.py`
reverses that mapping, so every token id becomes the exact text it appends to
the output. Tokens that do not decode to complete UTF-8 (partial multi-byte
sequences) are discarded: they could never be appended to a JSON string
safely.

### 3. Choosing the function (the LLM decides)

The decoder must pick one of the function names, and only the model's logits
decide which. All candidate names (each followed by a closing quote) are
walked simultaneously as a prefix trie:

- at each step, the valid tokens are those whose text is a prefix of at least
  one remaining suffix;
- the token with the highest logit among the valid ones is selected;
- when several names share a prefix (`fn_greet` / `fn_greetings`), the choice
  is deferred until the logits disambiguate them, and the closing quote
  competes with longer continuations.

The function is therefore chosen by the LLM itself — no heuristic, no keyword
matching. When only one candidate continuation remains, the decoder skips the
model call entirely (optimisation).

### 4. Decoding numbers (state machine)

A small state machine tracks the number being built and decides which
characters may extend it: a leading `-`, no leading zeros (`0` may only be
followed by `.`), a single fractional dot, no trailing dot. A precomputed list
of tokens made only of `0-9.-` is filtered through the machine at each step,
so multi-digit tokens (`265`) are handled naturally. The number ends when the
model's **unconstrained** best token is not a number continuation — i.e. the
model itself wants to move on to the next JSON fragment. The decoded text is
then converted to `int` or `float` (a stray trailing dot is dropped, an empty
value falls back to `0`).

### 5. Decoding strings (focused echo prompt)

Raw completion right after `..."parameters": {"name": "` turned out to be the
weak spot of a 0.6B model: it happily rambles meta-commentary instead of
writing the value (see *Challenges faced*). String values are therefore
extracted with a dedicated short prompt that ends right before the value:

```text
Question: Greet shrek
name: "
```

From there, content tokens are constrained to complete, escape-free UTF-8
fragments containing no quote, no backslash and no control character (so no
string can ever break the JSON), and the value ends when the model prefers the
closing quote, or when its unconstrained best token is neither content nor the
quote (it wants out of the string), or at a 200-character cap. A first content
token may not start with whitespace.

### 6. Booleans, integers, null

Booleans are decoded as the literals `true`/`false` with the same prefix-trie
mechanism as function names; `integer` reuses the number machine without the
dot; `null` is emitted directly.

### 7. Guaranteed validity

The decoder tracks the values it produces (`int`, `float`, `str`, `bool`,
`None`) while assembling the JSON text. After generation the text is parsed
with `json.loads` and validated against the function schema (exact keys,
exact types) as a self-check; only then is the call kept. The output file
contains exactly the `prompt` (echoed from the input), `name` and `parameters`
keys. Should anything unexpected still fail, the pipeline falls back to a
schema-compliant call with default values and logs a warning instead of
crashing.

## Design decisions

- **Plain completion, not chat template.** The SDK exposes raw next-token
  logits; the decoder works directly with them, which is exactly the level
  constrained decoding needs.
- **Greedy selection among valid tokens.** Picking the argmax of the
  schema-valid candidates is deterministic, reproducible during a review, and
  achieves the accuracy targets.
- **Structure owned by the decoder, values owned by the model.** The model
  decides the function name and the argument *values*; the decoder decides
  everything syntactic. This is what makes the JSON 100% valid.
- **Focused sub-prompts for strings** instead of one long generation: better
  extraction accuracy and shorter sequences, hence faster forwards passes.
- **No few-shot examples.** Experiments showed a single example biases the
  function choice heavily (the model copies the example's function), which is
  worse than the gain it brings on values.
- **pydantic everywhere.** Function definitions, prompts and results are
  pydantic models; malformed input files (missing, invalid JSON, unknown
  types, duplicate names, non-array content) are rejected with explicit
  messages before the model is even loaded.
- **Only the public SDK surface.** The code uses `encode`,
  `get_logits_from_input_ids`, `get_path_to_vocab_file` and `decode` — no
  private attribute of `llm_sdk` is touched, and neither torch nor
  transformers is imported by the project code (they are only runtime
  dependencies of the provided SDK).
- **Logits memoisation.** Identical id prefixes are cached (bounded FIFO), so
  repeated queries of the same sequence cost nothing.

## Performance analysis

Measured on a laptop-class CPU (Qwen3-0.6B, float32):

- **Validity**: 100% of the generated objects parse with `json.loads` and
  match the schema — by construction, not on average.
- **Accuracy**: 7/7 correct on the sample file (function *and* arguments),
  including multi-token numbers (`265 + 345`, `999999 + 1000001`), floats
  (`19.99`), strings with spaces and capitals (`total price`, `Kristoff`).
- **Speed**: ~3.5 s per simple prompt, ~8 s for a mixed string+number
  function; a 7-prompt file processes in ~25 s of generation (well under the
  5-minute budget), model loading excluded.
- The dominant cost is the repeated forward passes (the SDK has no KV cache);
  the single-candidate shortcut and the logits cache remove a large share of
  them.

## Challenges faced

- **`llm_sdk` import failure.** Copying the whole provided repository nested
  the package one level too deep (`llm_sdk/llm_sdk/__init__.py`), so Python
  found an empty namespace package. Flattening it next to `src/` fixed the
  import; the SDK's dependencies were moved into the project's
  `pyproject.toml` so `uv sync` alone prepares everything.
- **2-D tensors from `encode`.** `encode` returns a `[1, seq]` tensor; passing
  `ids.tolist()` (a nested list) to `get_logits_from_input_ids` silently builds
  a 3-D input. Flattening with `squeeze()` fixed the exploration script.
- **Strings were the hard part.** With the obvious prompt, the model rambles
  (`"1, ...}}? Is the function call correct? Explain why?"`) instead of writing
  the value. Moving string extraction to a focused echo prompt fixed both
  accuracy and speed.
- **Few-shot backfired.** A single worked example made the model copy the
  example's function name for every prompt; dropped in favour of the echo
  approach.
- **Termination rules.** Knowing *when* a value ends cannot be hardcoded:
  numbers end when the model prefers a non-digit token, strings when the
  model prefers the quote or wants out. Both rules were validated with a
  scripted fake model in the test suite.

## Testing strategy

- **Unit tests without the real model.** `tests/fake_model.py` implements the
  public SDK surface with a tiny vocabulary and a script of preferred tokens;
  the state machines (number shapes, leading zeros, literals, name
  disambiguation) and the full `generate_call` flow are tested
  deterministically (33 tests: `make test`).
- **Real-model checks.** The sample file (7 prompts) plus edge-case files:
  empty prompt, very large numbers, integer/float/string/boolean mixes,
  unknown names, and custom `--input/--output/--functions_definition` paths.
- **Error handling checks.** Missing files, invalid JSON, non-array content,
  unknown parameter types, duplicate function names: all produce a clear
  `error: ...` message and exit code 1, before any model load.
- **Static analysis.** `make lint` (subject flags) and `make lint-strict`
  (`mypy --strict`) both pass on the whole tree.

## Resources

- [Hugging Face: Qwen/Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B) — the model wrapped by `llm_sdk`
- [pydantic documentation](https://docs.pydantic.dev/) — data validation
- [uv documentation](https://docs.astral.sh/uv/) — project and dependency management
- [mypy documentation](https://mypy.readthedocs.io/) — static type checking
- [flake8 documentation](https://flake8.pycqa.org/) — style checking
- GPT-2 byte-level BPE encoding (the scheme Qwen reuses), described in the
  [tiktoken / GPT-2 encoder notes](https://github.com/openai/tiktoken)
- Constrained / guided decoding: the
  [Outlines documentation](https://outlines-dev.github.io/outlines/) explains
  the technique this project re-implements from first principles (the package
  itself is forbidden by the subject)

### How AI was used

AI assistants (Mistral's Vibe) were used to: explore and debug the provided
`llm_sdk` (import path, tensor shapes), design and iterate on the prompt
templates against the real model, draft the constrained-decoding state
machines, write the test harness, and prepare this README. Every generated
piece was reviewed, tested and reworked; the prompt-template experiments
(few-shot bias, string rambling) and their measured results in this README
come from runs executed and inspected locally.
