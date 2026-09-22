# How RunLobby measures agent activity

RunLobby reads local Codex and Claude JSONL files. Classification, aggregation and
display use Python rules. The monitor never asks an LLM to label or summarize a
session, runs commands from a transcript, or uploads a transcript.

## Evidence behind the categories

The taxonomy starts with two published sources, rather than inferred task intent:

- **SWE-agent**, Yang et al., NeurIPS 2024, distinguishes search/navigation,
  file viewing and file editing in its agent-computer interface. Those observable
  operations become separate RunLobby categories.
  [Paper, section 3 and appendix A](https://arxiv.org/html/2405.15793v3).
- **TraceLab**, Zhu et al., 2026, studies everyday Claude/Codex workloads. Its
  tool-category experiment uses explicit provider-tool mappings for execution,
  file operations, agent/task actions, web/remote lookup, planning and other
  operations. It reports invocation counts separately from measured tool latency.
  [Paper](https://arxiv.org/abs/2606.30560),
  [authors' category methodology](https://github.com/uw-syfi/TraceLab/blob/main/artifacts/tool_calls/tool_category_distribution/README.md).

RunLobby's finer execution categories are an engineering extension, **not a
universal taxonomy proven by those papers**. TraceLab's shell-command analysis
motivates looking inside shell calls instead of labelling every command "Bash".
[Authors' command methodology](https://github.com/uw-syfi/TraceLab/blob/main/artifacts/tool_calls/bash_command_breakdown/README.md).

Taxonomy version 1:

| Family | RunLobby categories | Observable evidence |
|---|---|---|
| File operations | Read; search/navigation; write/edit | Native Read/Edit/Glob tools, recognized shell executable and flags |
| Execution | Tests; build/lint; dependencies; version control; CI monitoring; other commands | Executable and recognized subcommand; e.g. `python -m unittest`, `cargo clippy`, `gh run view` |
| Remote lookup | Web/remote | Search/fetch tools and MCP calls; the last are deliberately broad |
| Coordination | Planning; subagents; wait/poll | Recorded plan, agent and wait tool names |
| Accounting | Mixed actions; no tool call; unclassified | Several categories in one request, model response without tools, or no applicable rule |

The top ten is a ranking of observed categories, not a requirement to invent ten
categories in every session. Unknown scripts, heredocs and substitutions remain
"Other commands"; strings inside a script are not evidence that a command ran.
Modern Codex records completed nested operations inside its `exec` wrapper. These
replace that wrapper in the action count; both are never counted together.

## What the numbers mean

- **Calls**: recorded tool invocations, not lines of code or successful tasks.
- **Time**: recorded tool duration when available; otherwise the interval between
  the call and its matching result. It can include waiting. Parallel durations
  can overlap; their sum is not elapsed session time. Missing durations stay unknown.
- **Tokens**: recorded model-request usage. Codex input already includes cache;
  Claude cache-read/cache-write counters are added to its uncached input. Reasoning
  is a subset of output, not an additional charge. Repeated content-block usage and
  Codex's duplicate modern/legacy events are deduplicated.
  When modern per-response usage exists for a turn, it supersedes that turn's
  legacy counters even if cumulative totals differ after resume or compaction.
- **Tokens by category**: a request belongs to one category only if all its linked
  calls have that category. Otherwise its tokens go to "Mixed actions". A response
  with no linked calls goes to "No tool call". This associates requests with
  observable actions; it does **not** isolate a command's causal token cost.
- **Repeated results**: identical recorded tool, arguments and result. Repetition is
  not automatically waste; it can be required polling. Missing results don't count.

Subscription allowance and API-equivalent price cannot be recovered reliably from
these counters. Neither a dollar bill nor a percentage of subscription quota is
invented. Exact usage counts do not make cross-model token totals equivalent costs.

## Reproducibility and limits

Rules live in `domain/activity.py`, provider decoding in `infrastructure/activity_logs.py`.
Tests use synthetic records matching observed schemas, including duplicate usage,
compound shell commands, cache accounting, partial lines and file truncation. The
test corpus records expected labels explicitly. It is a regression corpus, not a
representative benchmark or a measured classification-accuracy claim.

The reader follows appended data every 250 ms. Data becomes visible only after the
provider writes it: this is live log observation, not access to hidden model state.
If several sessions could match a launch, RunLobby asks for a selection with F9
instead of silently attributing another terminal's activity to this one.

The side pane is built into RunLobby. It uses a PTY on macOS/Linux, ConPTY on
Windows, and a virtual terminal screen for composition. It does not depend on a
particular terminal application or an external terminal multiplexer.

Linked subagent logs join the selected session using Codex parent-thread metadata
or Claude's per-session subagent directory. Discovery runs every two seconds;
already discovered logs are read every 250 ms. Provider response IDs and hashes of
legacy usage records prevent counting copied history twice. Missing or deleted
logs cannot contribute statistics. Unsupported terminal extensions such as inline
images are not rendered by the virtual screen.
