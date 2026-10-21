# Replay priority controls

In Replay & scenarios, prepare a replay or start automatic replay. The results
section shows Critical, High, Low (Normal), and processing-failure counts for all
events already processed in the current run.

- **Filter replay priority** selects Critical, High, Low (Normal), failures, or all.
- **Sort replay results** selects recorded order, most recent first, highest
  priority first, or lowest priority first. Priority ties retain recorded order;
  failures and missing priorities stay after known priorities when sorting by severity.
- **Previous/Next replay results** browse matching events ten at a time. Filtering
  and sorting use the full accumulated event list before pagination, not just the
  ten most recently processed events.
- Each result retains its original replay-record number and case link.

The existing decision policy returns Critical, High or Normal. The filter calls
the last level **Low (Normal)** to explain that Normal is the lowest existing
operational priority; it does not introduce a new model label or risk threshold.
This is distinct from a model's Low/Medium/High risk classification.

Filters only change the visible results. They do not change model predictions,
case priorities, source records, replay sequence, progress or saved events. Counts
update as replay advances. Starting a new run resets these view controls.

If a replay has produced only Normal cases, Critical and High counts correctly
remain zero and selecting either gives an explanatory empty state. A filter
cannot create those priorities or claim that unprocessed records were evaluated.
The original replay limits (100 records in the UI, 500 through the API), scenario
presets, source selectors and serving models are unchanged.

For a review, inspect any Critical/High cases actually produced by a run. The
separate depleted-stock, supplier-pressure or combined stress presets can also
demonstrate the system under modified conditions, but their outputs remain
synthetic case evidence, not historical replay events or accuracy measurements.
