# ADR 0102: Let the Public API Set a Job's Retry Budget

## Status

Proposed.

Related: ADR 0007, ADR 0011, ADR 0028 and ADR 0054.

## Context

The reconciliation loop puts a reclaimed job back on the queue while
it has retries left, and fails it once they are spent (ADR 0007, ADR
0011). Job.max_retries holds that budget, and the Postgres and SQLite
repositories already store it.

POST /jobs could not set it. CreateJobRequest had no field for it, and
CreateJobService built every Job with the default of 0. So every job
created through the public API had no retries. When its worker died,
reconciliation reclaimed it and failed it outright, even with an idle
worker on a healthy node. POST /jobs/{id}/retry then answered 200 and
left the job FAILED, because the budget was already spent. The answer
gave no way to tell that case from a job that was not FAILED.

This was seen on a two-node cluster at commit 49048b6. A 40-second job
was running when its agent was killed. The lease ran out after 30
seconds, the job went to FAILED, and the retry call answered 200 with
the job still FAILED.

## Decision

1. CreateJobRequest takes an optional max_retries. It defaults to 0,
   the value every job had before, and accepts 0 to 10.
2. CreateJobService takes max_retries and sets it on the Job. It
   refuses a negative value, so a caller other than the API cannot
   store one.
3. GetJobResponse carries max_retries and retry_count. It is the
   response of GET /jobs/{id}, POST /jobs/{id}/cancel and
   POST /jobs/{id}/retry.
4. POST /jobs/{id}/retry keeps its behavior. A job that cannot be
   retried is returned unchanged with 200. The two new fields show
   why: retry_count has reached max_retries.

Setting max_retries needs no scope. It only lets the scheduler run
work the caller was already allowed to submit, and a command still
needs jobs:execute (ADR 0054).

## Consequences

- A job created through the API can now survive the loss of its
  worker without an operator, as the README describes.
- A caller that omits the field gets the same behavior as before.
- One broken job can hold a node for at most 11 runs. The limit of 10
  is a guess and can be raised.
- Clients that read GetJobResponse get two more fields. Nothing is
  removed or renamed.

## Not Claimed

- That a retried job runs once. A job retried after a lost lease may
  run again from the start. Retries do not change the rule that a
  stale owner cannot report an outcome (ADR 0034, ADR 0036).
- That the first retry lands on a healthy node. See Progress.

## Alternatives Considered

- **Answer 409 when a retry is refused.** Rejected. The route chose
  200 on purpose, and its docstring says why. Showing the budget keeps
  that choice and still tells the caller what happened.
- **A server-wide default above 0.** Rejected. It would change the
  behavior of every existing caller, and a job that should not rerun
  would rerun.
- **Require a scope to set max_retries.** Rejected for now. A retry
  runs no command the caller could not already run.

## Progress

2026-11-16. The full suite passed with the change: 1585 passed and 27
skipped against Postgres. ruff and mypy were clean.

2026-11-16. On a two-node cluster, a job with max_retries 3 was running
when its agent was killed. The lease ran out at 30 seconds and the job
was requeued with retry_count 1. It was scheduled back onto the dead
node, because that node had not yet missed its 60-second heartbeat
timeout and its worker still read as IDLE. The lease ran out again,
and the second retry placed it on the healthy node, where it finished
with exit code 0 at 104 seconds. With max_retries 1 it would have
failed. Keeping a job away from a node whose worker just lost its lease
is a separate change.

## How to Verify

    pytest -q tests/presentation/test_job_retry_budget_api.py \
        tests/presentation/test_create_job_request_schema.py \
        tests/application/test_create_job_service.py
