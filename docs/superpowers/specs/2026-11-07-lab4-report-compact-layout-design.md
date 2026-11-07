# Lab 4 Report Compact Layout Design

## Intent

Reformat the existing Lab 4 Software Testing Report so it looks like a polished academic submission rather than a document assembled from individually forced pages. Preserve every assessed black-box and white-box item while reducing avoidable empty space.

## Goals

- Retain all 17 black-box cases and all 12 white-box basis-path cases.
- Retain equivalence classes, boundary-value analysis, both control-flow graphs, both cyclomatic-complexity calculations, expected and actual results, execution evidence, Manual compliance, limitations, and conclusion.
- Reduce the report from 12 pages to approximately 9-10 pages when this can be done without harming legibility.
- Remove unnecessary forced page breaks and rebalance section transitions.
- Resize the two control-flow graphs so the source excerpt, explanation, graph, and related evidence use the page efficiently.
- Keep table text readable when printed on A4 paper.

## Non-goals

- Do not remove, summarise away, or rename any assessed test case.
- Do not change test code, application behaviour, calculations, results, or requirement mappings.
- Do not introduce landscape pages or a separate appendix.
- Do not change the established green, gold, cream, and white visual identity.

## Constraints

- The report remains an English, portrait-A4 PDF.
- Case identifiers must remain identical to the automated test names and JUnit evidence.
- The first CFG must remain N=13, E=18, V(G)=7; the second must remain N=11, E=14, V(G)=5.
- All Manual 3.2.1-3.2.4 evidence must remain directly visible.
- The final PDF must be rendered page by page and visually inspected for clipping, overlap, broken tables, awkward isolated headings, and excessive blank regions.

## Approaches Considered

1. **Compact academic report - selected.** Keep portrait A4, reduce graph height, let related sections flow naturally, and use page breaks only at meaningful major transitions. This preserves a familiar submission format and improves page density.
2. **Main report plus appendix.** Shorter main narrative, but makes the marker jump between the report and detailed test evidence.
3. **Mixed portrait and landscape pages.** Maximises table width, but creates inconsistent viewing and printing orientation.

## Chosen Layout

- Keep the cover as a deliberate visual pause rather than treating its whitespace as a defect.
- Combine the executive summary and test-design material more efficiently where natural flow permits.
- Keep the full black-box result table together or split it only with repeated headers.
- Present each white-box method as a compact two-page unit: explanation/source/CFG, followed by complexity and path results.
- Allow execution evidence, compliance, limitations, and conclusion to flow without forced single-purpose pages when space permits.
- Target 9-10 pages; visual quality and readability take priority over hitting an exact page count.

## Acceptance Checks

- PDF text contains all 29 unique case IDs and every required Manual token.
- JUnit-to-report case-name equality still holds.
- Both complexity formulas and path counts remain correct.
- All pages render successfully and pass full-page visual inspection.
- No meaningful page has a large avoidable blank region caused by manual pagination.
