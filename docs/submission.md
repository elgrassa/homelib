# Submission runbook — LLM Zoomcamp 2026

**Deadline: 2026-09-08, 01:00.** This is attempt 3 and the last one, so the
sequence below is written to be executed under time pressure without thinking.

Referenced by `just publish`, which refuses to push unless Forgejo CI is green.

---

## What gets submitted

A **public GitHub URL** pointing at a repository a stranger can clone and run.
That is the one place this project deviates from the studio's Forgejo-only
rule, and the deviation is scoped deliberately:

- **Forgejo (`forgejo` remote) stays authoritative.** Branches, PRs, CI, code
  review, and history all live there.
- **GitHub (`public` remote) is a one-way publication target.** It receives
  `main` only, because the course requires a URL graders can open without an
  account. Nothing is developed there, no PR is opened there, and its Actions
  are irrelevant — CI is `.forgejo/workflows/` only.

Setting up the public remote:

```bash
git remote add public git@github.com:elgrassa/homelib.git
```

If that repository does not exist yet, create it on GitHub as **public**, with
no README, no .gitignore and no licence file — anything GitHub generates would
collide on the first push.

## Preconditions — all of these, not most

Run through this list in order. Each line is a command, not a judgement call.

```bash
# 1. Local gates green. Not "green last time" — now.
just ci

# 2. The stack actually comes up, and every service reports healthy.
just up && just ps

# 3. The reviewer path works from an empty directory: clone, seed, ask,
#    and get an answer whose citation resolves. This is the only check that
#    catches "works on my machine".
just drill

# 4. Forgejo CI green on the branch being published.
#    `just publish` re-checks this and refuses otherwise.
```

`just drill` is the one that matters most. It clones into a fresh directory on
offset ports, brings the stack up from scratch, tears down its own volumes
afterwards, and requires a real answer with a **resolvable** citation and
`degraded is False`. A green `just ci` proves the code is consistent with
itself; only the drill proves a stranger can run it.

## Publishing

```bash
just publish
```

It verifies Forgejo CI status for the current branch, pushes `HEAD:main` to
`public`, and prints the exact commit SHA. **Record that SHA in the submission**
— it pins what was graded, so later work on the repo cannot be mistaken for
what was submitted.

## Before pasting the URL, open it as a stranger

Log out of GitHub (or use a private window) and load the repository URL.
Check, in this order:

1. The README renders, and the first screen states the problem — not the tech.
2. The quickstart is copy-pasteable and does not assume anything local.
3. No `.env`, no key, no personal ebook, nothing under `data/books/`.
4. `data/corpus_snapshot.jsonl.gz` is present — this is what lets a reviewer
   seed the database without downloading 18 books.
5. `docs/evidence.md` and `CHECKLIST.md` are readable, since they are the
   fastest way for a grader to see what was verified rather than claimed.

Point 3 is worth a real check rather than a glance: the repository is public
and permanent, and git history cannot be un-published.

## Peer reviews — do not skip these

**Three peer reviews are required, and they carry up to +9 points**, more than
any single graded criterion in the project itself. They are also the easiest
points in the entire course to lose, because they happen *after* the relief of
submitting.

Block at least **2 hours immediately after submitting**, while the rubric is
still fresh. Reviewing someone else's project the day before the review
deadline, on a different set of criteria than the one just internalised, is how
these get dropped.

## Final-day order of operations

Written as a sequence because on the last day the temptation is to do the
interesting work first.

1. `just ci` — green.
2. `just drill` — green.
3. Push to Forgejo; wait for CI green.
4. `just publish`; record the printed SHA.
5. Open the public URL logged out; run the five checks above.
6. Submit the URL.
7. Schedule the three peer reviews **before** closing the laptop.

## If something is red at the deadline

Submit anyway, with the gap stated plainly in the README and `CHECKLIST.md`.

A working project with one honestly documented gap scores better than a project
that claims completeness a grader can disprove in one command — and every
criterion is scored independently, so one red area cannot take the others down
with it. `CHECKLIST.md` §E exists for exactly this: it is already written to be
read by someone else.
