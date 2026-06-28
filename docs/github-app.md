# Registering the GitHub App

You only need this for the *automated* "file an issue → get a PR" flow. The
local CLI and dashboard work without it.

1. **Create the App**: GitHub → Settings → Developer settings → GitHub Apps → New.
   - Webhook URL: `https://<your-host>/api/webhook/github` (use `ngrok http 8000`
     for local testing).
   - Webhook secret: generate a random string → put it in `.env` as
     `GITHUB_WEBHOOK_SECRET`.
   - **Permissions**: Repository → *Contents: Read & write*, *Pull requests:
     Read & write*, *Issues: Read*.
   - **Subscribe to events**: *Issues*.

2. **Generate a private key** (bottom of the App settings page). Download the
   `.pem`, save it in the repo root as `github-app-private-key.pem`
   (gitignored), and set `GITHUB_PRIVATE_KEY_PATH` + `GITHUB_APP_ID` in `.env`.

3. **Install the App** on a test repository.

4. Open an issue in that repo. The webhook fires `issues/opened`, the pipeline
   runs in the background, and a PR appears on branch `codegen/issue-<n>`.

### How auth works (in `app/services/github.py`)
- The App signs a short-lived **JWT** (RS256) with its private key.
- That JWT is exchanged for an **installation access token** scoped to the repo.
- Files are committed atomically via the **Git Data API** (blobs → tree →
  commit → branch ref), then a PR is opened.

### Closing the learning loop on real PRs (next step)
Subscribe to `pull_request` (closed/merged) and `pull_request_review` events and
route them to `services.learning.record_feedback` so merges/rejections teach the
system automatically. See the roadmap in the main README.
