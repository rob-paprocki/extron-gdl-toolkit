# research/2026-09-10

The measurement scripts behind the 2026-09-10 findings, kept so each number in
the commit messages and docs can be reproduced rather than taken on trust. Run
them from the repo root after `git lfs pull` (they read `seeds/` and
`archive/job-9fe2c865/`).

`seeds/` now also holds the 835 seed, so a rerun that globs every seed counts
one project more than the figures quoted below, which were taken over the 13
seeds plus the Liberty Bank fixture.

| Script | Question | Answer at the time |
|---|---|---|
| `inventory.py` | What is in each seed? | 13 seeds, 6 theme families, 7-13 pages and 176-878 controls each - full All-inclusive templates, not blank projects. |
| `retarget_truth.py` | Does `retarget --scale` reproduce Extron's own 1535 from their 1035? | 22.2% of controls identical; 504 of 505 misses are over 4px. |
| `fit.py` | What transform did Extron actually use? | Per-axis linear, R² ≈ 0.9997 on all four rect components; slopes 1.507 / 1.366 against our 1.5 / 1.35. The residual is hand-nudging, not a different rule. |
| `popups.py` | Were the popups resized? | All 29. Full-canvas ones by 1.5×1.35; the ten 880×525 cards by 1.405×1.383. |
| `layout.py` | Is a popup's authored size its real size? | Yes - the built `layout.json` matches the authored canvas for all 29, including 880×525. This is what disproved "a popup is always full-canvas". |
| `built_check.py` | Did our retargeted build come out right? | 650/650 planned controls where planned, 0 relocated to 0,0, 10 popups at 1320×709. 22.2% identical to Extron's hand-authored 1535, median 18px. |
| `states.py` | Do buttons really change between states? | 3602 buttons with 2+ states; 60.4% change fill, 67.9% change artwork. |
| `statenames.py` | What are states called? | `('Off', 'On')` for 3475 of 3668 buttons (94.7%). `TLPPressFeedbackStateID` is -1 on 7320 of 7392 states - press feedback is not the idiom. |

`tests/audit_corpus.py` is the maintained successor: it re-tests these beliefs,
and the rest of the repo's, against every project it can reach.
