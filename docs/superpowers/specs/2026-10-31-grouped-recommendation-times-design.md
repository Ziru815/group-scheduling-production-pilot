# Grouped Recommendation Times Design

## Intent

Make the Best matches page feel like a decision aid rather than a raw list of
candidate combinations. When one venue has many equally ranked overlapping
times, show one venue card with selectable times instead of repeating the same
venue, score and travel facts for every 15-minute start.

## Goals

- Keep every valid time available for selection and final confirmation.
- Reduce repeated cards without hiding materially different attendance or
  travel outcomes.
- Preserve the current ranking, stale-result protection, organiser-only
  confirmation and missing-routing labels.
- Make the selected date and time explicit before confirmation.

## Non-goals and anti-goals

- Do not change the recommendation formula, candidate generation interval,
  venue shortlist or backend API.
- Do not silently discard later times merely to shorten the page.
- Do not combine options that have different attendees, absence reasons,
  feasibility state, score or travel facts, even when the venue is the same.
- Do not invent a continuous time range: the user must choose a real stored
  Combination that the backend can confirm.

## Constraints

- FR-E1/UC-11 still require ranked venue-and-time recommendations.
- UC-12 confirmation must submit the exact `combinationId` selected by the
  organiser.
- The API currently returns a flat ranked list, and production data must remain
  backward compatible.
- The UI must remain usable on the existing mobile-first layout.

## Approaches considered

1. **Group in the results UI (chosen).** Retain the flat API response, group
   equivalent combinations locally, and let the organiser choose a stored time
   inside each card. This removes repetition with no data loss or API migration.
2. **Deduplicate in the backend.** Return only the earliest time for each venue.
   This is simpler to display but removes legitimate choices and can recommend
   a time the group likes less.
3. **Only show the first few raw results.** This shortens the page but leaves the
   duplication problem intact and may hide the first result for another venue.

## Design

### Equivalence and grouping

Add a pure frontend grouping helper. Two combinations belong to the same group
only when all of the following match:

- venue ID;
- feasibility status;
- combined, attendance and travel scores;
- total, average and maximum travel minutes;
- attendee IDs and each attendee's transport/routing/travel facts;
- absentee IDs and attendance statuses.

Start/end times, rank and `combinationId` are deliberately excluded. This means
that equal-looking scores alone cannot accidentally merge options for different
people. Groups retain the order of their highest-ranked member, and their time
options remain in chronological order.

### Results page

- Render one ordered-list item per group. Display ranks as consecutive group
  ranks (`#1`, `#2`, `#3`) so removing visual duplicates does not produce a
  confusing jump from `#1` to `#12`.
- The first group is the Top match.
- A collapsed group shows the venue, selected time, score, attendance/travel
  summary and, when applicable, “11 time options”.
- Expanding a group reveals the existing explanation, people, venue source and
  score breakdown plus an **Choose a time** section.
- Time choices are real combinations, rendered as accessible buttons. The
  earliest option is selected initially. Selecting a different time updates the
  visible time and the exact combination used by confirmation.
- Show the first six time choices initially; a “Show all N times” control reveals
  the rest. This prevents a long multi-day availability window from becoming a
  second wall of controls.
- Feasible and data-unavailable groups remain separated by the existing warning.
  Data-unavailable times cannot be confirmed.
- If a confirmed combination belongs to a group, that exact time is selected and
  the card receives the Confirmed choice label.

### Confirmation and state

The Results page tracks the expanded group and the selected `combinationId` for
each group. `ConfirmPlanPanel` and the confirm mutation receive the selected
combination, not merely the group's first option. Regeneration resets selections
to each group's first ranked option. Stale and read-only behaviour is unchanged.

### Accessibility and responsive behaviour

- Each time button exposes the full date/time text and a selected state.
- Keyboard users can expand a group and choose a time without relying on colour.
- Time buttons wrap on narrow screens and maintain touch-friendly targets.
- Group labels announce the group rank and number of available time options.

## Verification

- Unit tests prove equivalent options group together, different attendee/travel
  outcomes stay separate, ordering is stable and confirmed selections are
  retained.
- Component tests prove a user can expand a group, reveal more times, select a
  later time and confirm its exact `combinationId`.
- Existing frontend tests, type-check and production build must pass.
- Production verification uses the reported session: Jurong Central Park's 11
  repeated cards should become one card with 11 time options, while Chinese
  Garden and Choa Chu Kang Park remain separate ranked groups.
