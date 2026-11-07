# Codex CLI access blocker

Model: `gpt-6.1-sol`; effort: `medium`; authentication: existing ChatGPT CLI login.
No API key or other provider was used.

The saved live E06 split experiment received an explicit CLI message:

> This content was flagged for possible cybersecurity risk.

The remainder directed authorized researchers to apply for Daybreak access before
retrying. This is a platform invocation rejection, not an actor response, monitor
detection, failed tool action, or demonstrated usage-quota exhaustion.

- Run: `r_dcc0ec6fb60d48caadf1`
- Focal role: r2, staging
- Decision: 0
- Call: `a_5cbe966b115d74a646b7e5c3`
- [Portable stop-marker record](../logs/graph_pilot/access_status.json)
- [Raw CLI events (local archive)](../logs/graph_pilot/raw/calls/157ce3174191ced2afacbe0b88d7b1159537506caf06ddf0bf2261dd94dfe1c3/attempt_1/stdout.jsonl)
- [Recorded result (local archive)](../logs/graph_pilot/raw/calls/157ce3174191ced2afacbe0b88d7b1159537506caf06ddf0bf2261dd94dfe1c3/attempt_1/result.json)

Other saved attempts returned HTTP403 from the CLI's connection to its normal
service. Their exact cause is not established; they are not automatically labeled
as safety rejections or usage limits. They affected both actors and monitors.
CLI login was still valid and a single harmless connectivity request succeeded.
No restricted prompt was retried or rephrased, and no alternate access route,
provider, API key, or model was used.

Both model batches are stopped. The local `logs/graph_pilot/raw/STOP_SECURITY`
file prevents new calls. The existing cached results, partial runs, and pending
jobs are retained. Offline tests, verification, and report generation work.

The user has been asked whether the account already has supported approved access
for these evaluations. OpenAI's [Models and Trusted Access documentation](https://learn.chatgpt.com/docs/cyber-safety)
describes approval requirements. The [CLI developer command documentation](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
describes `/daybreak` for accounts/models with access. Selecting a program does
not itself grant access. No claim is made here that this account has or lacks an
entitlement; the local profile contains no explicit saved program selection.

After access is resolved, any change to model access behavior must be recorded in
a new experimental configuration. Do not silently mix standard-access and
approved-program results or treat earlier rejected requests as successful calls.
