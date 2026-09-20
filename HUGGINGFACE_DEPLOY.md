# Deploying the public demo to Hugging Face Spaces

This packages the exact same webapp you run locally (`python3 webapp/server.py`)
into a container Hugging Face runs for you, reachable at a public URL. No code
changes are needed beyond what's already in this repo (`Dockerfile`,
`.dockerignore`, and the `PORT`/`0.0.0.0` handling in `webapp/server.py`).

**Known limitation of the public demo** (stated up front, not discovered later):
the webapp keeps its last audit run in a single in-memory `STATE` dict, not a
per-visitor session. On a shared public Space, one visitor's "Run Audit" result
is what everyone else sees until someone runs it again. That's fine for a demo
(the "Load sample ACME dataset" button gives everyone the same clean starting
point), but it is not multi-tenant — see the Architecture Guidebook doc for
what a hosted, multi-user version would need instead.

## 1. Create the Space

1. Go to https://huggingface.co/new-space (create a free account first if you
   don't have one).
2. Fill in:
   - **Space name**: e.g. `itgc-audit-ai`
   - **License**: your choice (e.g. MIT)
   - **Space SDK**: choose **Docker** (not Gradio/Streamlit — this app ships
     its own Dockerfile)
   - **Space hardware**: the free CPU tier is enough
   - **Visibility**: Public (so it's reachable without a login)
3. Click **Create Space**. HF creates an empty git repo at
   `https://huggingface.co/spaces/<your-username>/itgc-audit-ai`.

## 2. Add the Space's own README front-matter

Every HF Space needs a small YAML block at the very top of its own
`README.md` telling HF how to run it. This repo's existing `README.md` is
project documentation, not that config block, so add the block to the very
top of it (HF only reads the front-matter; the rest of the file still
displays underneath as the Space's description):

```yaml
---
title: ITGC Audit AI
emoji: 🛡️
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---
```

Insert that block as the first thing in `README.md` (above the existing
`# ITGC Audit AI` heading), then save.

## 3. Push this repo to the Space

Hugging Face Spaces are git repos (with git-LFS for large files, not needed
here). From this project's root:

```bash
# one-time: tell git who you are, if this environment hasn't already
git init                                   # skip if already a git repo
git add -A
git commit -m "Initial commit: ITGC Audit AI"

# add the Space as a remote (use an access token as the password when prompted,
# from https://huggingface.co/settings/tokens - a "write" token)
git remote add space https://huggingface.co/spaces/<your-username>/itgc-audit-ai
git push --force space main:main
```

If your default branch is `master` instead of `main`, push
`master:main` instead — HF Spaces expects the branch named `main`.

## 4. Watch it build

On the Space's page, open the **Logs** tab. HF will:
1. Build the Docker image (`pip install`, then generate the bundled ACME +
   hard-scenario datasets — this takes a minute or two the first time).
2. Start the container (`python3 webapp/server.py`), which binds `0.0.0.0:7860`
   because `PORT=7860` is set in the Dockerfile.
3. Once it prints "Application startup complete", the **App** tab shows the
   live webapp, and the Space's URL
   (`https://<your-username>-itgc-audit-ai.hf.space`) is what you share.

## 5. Updating the demo later

Any time you want to push a new version:

```bash
git add -A
git commit -m "Update: <what changed>"
git push space main:main
```

HF rebuilds automatically on every push.

## 6. Optional: keep the Space private, share selectively

If you'd rather not make it fully public, set **Visibility: Private** in step
1 and use HF's "Share" link feature to give specific people access without
making the Space discoverable — useful for showing your MD a live link
without opening it to the world.
