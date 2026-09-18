# Evidence

Raw output from the runs the README quotes. Each file is the unedited stdout of one command, kept
small on purpose so the claims stay checkable without a re-run.

## `live-comparison/`

The two-chooser loop comparison in the README's benchmark section: the same task file
(`examples/wikipedia-chain.json`), the same start page, the same postconditions, one pass per file.

```
jev-pilot run --start https://en.wikipedia.org/wiki/Calculator \
  --task-file examples/wikipedia-chain.json --provider jev --headless

jev-pilot run --start https://en.wikipedia.org/wiki/Calculator \
  --task-file examples/wikipedia-chain.json --provider openai \
  --model <a free open-weights chat model> --base-url <an OpenAI-compatible relay> --headless
```

| file | arm | tasks reached | per-decision latency |
|---|---|---|---|
| `pass1-jev.txt` | Jev | 3 of 3 | 982, 386, 338 ms |
| `pass2-jev.txt` | Jev | 3 of 3 | 939, 310, 302 ms |
| `pass1-chat-model.txt` | a chat model | 2 of 3 | 6,449, 10,331 ms, then a call that never returned |
| `pass2-chat-model.txt` | a chat model | 2 of 3 | 3,636, 2,733 ms, then a call that never returned |

Two edits, both noted here rather than hidden: the relay's base URL is replaced with
`<local OpenAI-compatible relay>`, and line endings are normalised. Nothing else is changed, and
the failures are left in, including the two that ended the run with exit code 1.

## `bench-decisions/`

The *frozen-state* bench from the same README section: 27 states captured from eight live Wikipedia
pages (`examples/bench-decisions.json`), replayed against three choosers.

| file | arms | what it shows |
|---|---|---|
| `run-a-jev-and-relay.md` | Jev, and the local relay's free model | Jev 25/27 with full coverage; the relay answered 1 of 27 (26 × `503 empty response content`) |
| `run-b-two-open-weights.md` | qwen3-30b-a3b-instruct, llama-3.1-8b-instruct | both answer all 27, and neither abstains once: 0/16 |
| `endpoint-failures.txt` | the endpoints that could not serve the bench | per-chooser error counts and verbatim messages: the OpenRouter free tier's `429` with its daily cap and reset time, and the relay's `503` |

The relay row is kept because a coverage failure is a result: it is why the reported open arms are
paid at their cheap rates rather than free. Only line endings are normalised here; the error text is
the endpoints' own.

Those two failures are transport failures, not wrong picks: the relay answered with an empty
response after about 30 s and 52 s. The element the model chose was the same element Jev chose in
every case where it answered at all.
