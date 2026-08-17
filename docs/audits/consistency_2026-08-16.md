# Consistency audit - 2026-08-16 session

**Scope.** Every number asserted this session, in `CHANGELOG.md [Unreleased]`, `README.md`'s
pasted transcript, `docs/audits/file_size_baseline.json`, and the five commits `e9f21a4`,
`7a990b1`, `eebcaf6`, `b4b9b13`, `cef769d`.

**Method.** Not a prose re-read. Every claim was RE-DERIVED by importing the live modules and
querying git, in `scratchpad/consistency.py`. Tolerance: exact match (these are counts, not
measurements). 20 claims checked.

**Result: 17 OK, 3 DRIFT.** All three drifts are class (A) - a value in the prose matching no
current source - and all three are mine, produced within hours of being written.

## DRIFT

| Claim | Asserted | Derived now | Verdict |
|---|---|---|---|
| `mutation_check.py` after the split | 377 | **387** | DRIFT - the `sys.path.insert` re-export fix was added AFTER the measurement |
| `mutation_entries_b.py` | 538 | **604** | DRIFT - eleven mutation entries were appended after the split |
| MUTATIONS table | 200 entries / 201 anchors | **211 / 212** | DRIFT AS READ - true of the split, but written as a bare fact |

None of the three is a false claim about the split itself; each was a correct measurement at
the instant it was taken. They are drift because they were written WITHOUT that instant, so a
reader takes them as current. That is the same failure as an undated benchmark, and this
project's whole thesis is that an undated measurement presented as a current fact is a bluff
regardless of who makes it.

**Fixed** in `CHANGELOG.md` and the baseline's `_split_2026_08_16` note: both now state the
figures as the measurement at the split AND give the current values. The five commit messages
are left untouched - they are the immutable record of what was measured when, and rewriting
history to make an old measurement look current would be the defect, not the fix.

## OK (17)

Verified against the live tree: `AUX_GATES` 16 rows; `SELFTEST_IS_THE_GATE` 5 adjudications;
`RECORDING_TIERS` 6 declared; file-size population 55 `.py` files (source: git);
`mutation_entries_a.py` 541; `mutation_check.py` at `c40b7ea` 1399; ship-bar 24 confirmed
report rows and a declared heading count of 24 that agrees with them; suite 38 selftests, and
the README transcript claims 38; 56 hook commands examined by the newly-enforcing
`hook-provenance`; review `wf_f63b9ccf-816` 41 produced / 41 adjudicated / 40 confirmed / 1
refuted, 46 agents, 5,474,884 subagent tokens.

## Note on one number that git cannot check

`1415` (the pre-split size of `mutation_check.py`) exists in NO commit: it was an intermediate
state between adding the MODE pins and performing the split, and the split was committed as one
change. It is supported by the `file-size` gate's own recorded output - `tools/mutation_check.py
grew 1399 -> 1415` in `scratchpad/suite2.log` - and by `1399` being independently confirmed at
`c40b7ea`. Recorded here so the claim has a stated provenance rather than resting on memory.

## Classes B, C, E, F

Not applicable: these deliverables contain no figures, no numbered tables, and no
cross-references. A scan for placeholder markers (`[TODO]`, `TBD`, `TKTK`, `[insert`) over the
changed prose found none.
