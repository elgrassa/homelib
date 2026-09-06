# Documentation licence

HomeLib / MagicLib documentation © 2026 Pavlo Korodziievskyi, CC BY-NC-SA 4.0

This covers the **documentation** in this repository: `README.md`, everything
under `docs/**` (prose and diagrams), other `*.md` files, and any screenshots
or mockups of the product. It is licensed under the **Creative Commons
Attribution-NonCommercial-ShareAlike 4.0 International** licence (CC BY-NC-SA
4.0):

- Human-readable summary: <https://creativecommons.org/licenses/by-nc-sa/4.0/>
- Full legal code: <https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode>

Attribution line to use when reusing this documentation:

> HomeLib / MagicLib documentation © 2026 Pavlo Korodziievskyi, CC BY-NC-SA 4.0

## What this licence does NOT cover

- **Source code.** All code in this repository (`apps/`, `packages/`, `tests/`,
  configuration, scripts, etc.) is licensed under **PolyForm Noncommercial
  1.0.0**, not CC BY-NC-SA — see the top-level `LICENSE` file.
- **Third-party datasets.**
  - Project Gutenberg texts used by the ingest pipeline are in the **public
    domain** (US) and carry Project Gutenberg's own trademark/usage terms for
    redistribution of their eBook headers.
  - Open Library metadata is used under **Open Library's own terms** for that
    metadata, not under this licence.
  - Pottermore metadata is **publisher-owned**; only titles and URLs are
    stored in this repository, never the underlying text.
- **Third-party model weights.**
  - `sentence-transformers/all-MiniLM-L6-v2` and
    `cross-encoder/ms-marco-MiniLM-L-6-v2` are distributed upstream under
    **Apache-2.0** by their respective authors.
  - Any Groq- or Ollama-hosted model used at inference time remains under
    that model's own licence, not under the terms of this repository.

If you are unsure which licence applies to a specific file, the rule of
thumb is: source code → `LICENSE` (PolyForm Noncommercial 1.0.0); everything
else described above → this file (CC BY-NC-SA 4.0), except the third-party
data and model exceptions listed above, which keep their own upstream terms.
