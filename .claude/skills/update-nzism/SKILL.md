---
name: update-nzism
description: Refresh the indexed NZISM document when a new version is released. Use when the user says there is a new NZISM version, asks to update or re-index the NZISM data, or provides a new nzism.xml.
---

# Update the NZISM data

Work from `nzism-mcp/` unless a step says otherwise. Background and pitfalls are in `AGENTS.md`.

1. **Get the XML.** The user must download it in a browser from https://nzism.gcsb.govt.nz/ism-document/xml (bot protection blocks curl; do not try to bypass it). Ask for the file path if you were not given one.
2. **Preview.** Run `./update.sh --check <path>`. Report the section counts (added, removed, changed) and the deeplink line. If it says the file is identical, stop.
3. **Apply.** Run `./update.sh <path>`. It overwrites `data/nzism.xml` and `data/nzism_index.json`.
4. **Update provenance.** Edit `data/README.md`: NZISM version, month, and today's download date.
5. **Deeplinks.** If step 2 reported added sections with no deeplink, tell the user `data/deeplinks.json` is stale and that no scraper exists. Do not invent anchor IDs.
6. **Smoke test.** Run `uv run python -c "import server; print(len(server.SECTIONS))"` and confirm it loads. The count is paragraphs (3991 at V.3.9), slightly more than the unique-ID count in the `update.sh` summary (3989), because some IDs repeat.
7. **Review and commit.** Show `git diff --stat`. Commit only if the user asks.
8. **Deploy is separate.** The live service only updates after `cd ../nzism-mcp-cdk && npx cdk deploy`. This changes production: run `npx cdk diff` first and get the user's explicit approval before deploying.
