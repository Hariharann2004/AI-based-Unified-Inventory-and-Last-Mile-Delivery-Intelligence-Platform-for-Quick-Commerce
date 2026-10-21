# Replay priority controls

In Replay & scenarios, prepare a replay or start automatic replay. The results
section shows Critical, High, Normal, and processing-failure counts for all
events already processed in the current run.

- **Filter replay priority** selects Critical, High, Normal, failures, or all.
- **Sort replay results** selects recorded order, most recent first, highest
  priority first, or lowest priority first. Priority ties retain recorded order;
  failures and missing priorities stay after known priorities when sorting by severity.
- **Previous/Next replay results** browse matching events ten at a time. Filtering
  and sorting use the full accumulated event list before pagination, not just the
  ten most recently processed events.
- Each result retains its original replay-record number and case link.

The existing decision policy returns exactly **Critical, High or Normal**. There
is no separate Low operational priority and the interface no longer uses a Low
alias. This is distinct from a model's Low/Medium/High risk classification.

Filters only change the visible results. They do not change model predictions,
case priorities, source records, replay sequence, progress or saved events. Counts
update as replay advances. Starting a new run resets these view controls.

If a replay has produced only Normal cases, Critical and High counts correctly
remain zero and selecting either gives an explanatory empty state. A filter
cannot create those priorities or claim that unprocessed records were evaluated.
Replay still selects up to 100 records in the UI (500 through the API). Optional
inventory start/end dates select which chronological period is replayed. The
separate mixed-priority demonstration selects saved historical assessments across
different periods without modifying model outputs. See [replay modes](replay-modes.md).

For a review, inspect any Critical/High cases actually produced by a run. The
separate depleted-stock, supplier-pressure or combined stress presets can also
demonstrate the system under modified conditions, but their outputs remain
synthetic case evidence, not historical replay events or accuracy measurements.
