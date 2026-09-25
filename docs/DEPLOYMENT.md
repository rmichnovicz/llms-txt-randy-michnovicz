# Deployment

Frontend: https://brief-llms-txt.pages.dev

Backend: https://api-production-e25ea.up.railway.app

Railway project: https://railway.com/project/acadd658-0641-4550-94ae-79a7b934f854

Cloudflare Pages serves the Vite build and proxies `/api/*` and `/health` to
Railway through `frontend/public/_worker.js`. Leave `VITE_API_BASE` unset for
this deployment. The proxy preserves cookies and streaming responses and disables
API caching. `API_ORIGIN` is configured as a Pages secret.

Railway runs managed Postgres plus three services:

| Service | Configuration | Behavior |
| --- | --- | --- |
| api | `railway.json` | Migrate before deployment, then serve HTTP on port 8000; health check `/health` |
| worker | `deploy/railway-worker.json` | Process durable crawl and generation jobs |
| scheduler | `deploy/railway-scheduler.json` | Enqueue due monitored projects hourly, then exit |

All services use `DATABASE_URL=${{Postgres.DATABASE_URL}}`. The API has
`BRIEF_SECURE_COOKIES=true`, `BRIEF_EMBEDDED_WORKER=false`, and
`FRONTEND_ORIGINS=https://brief-llms-txt.pages.dev`. The worker has the configured
OpenAI key and model. The API requires a private creation key, stored locally in
the gitignored `.env.deploy` file as `BRIEF_CREATION_KEY`; enter its value in the
home page's creation-key field. Existing projects remain accessible with their
private links. Never include the key in a frontend build or repository.

## Redeploy

Authenticate with `npx @railway/cli login` and
`frontend/node_modules/.bin/wrangler login` when sessions expire.

```sh
uv run python scripts/deploy_backend.py api
# Wait for the API's migration and health check to succeed before these:
uv run python scripts/deploy_backend.py worker
uv run python scripts/deploy_backend.py scheduler

npm --prefix frontend ci
npm --prefix frontend run build
cd frontend
npx wrangler pages deploy dist --project-name brief-llms-txt --branch main
```

The backend script applies the selected JSON configuration as Railway service
settings, then uploads only runtime source, lockfile, package metadata,
Dockerfile, and the chosen service configuration. Local environment files,
research, tests, and assignment documents are excluded from the upload. It
returns after upload; check Railway deployment status before declaring success.
Deployments are CLI uploads; GitHub autodeployment is not configured.

## Verification

```sh
node --test frontend/tests/proxy.test.mjs
curl --fail https://brief-llms-txt.pages.dev/health
```

Also verify a private project can be created, its session cookie exchanged, its
crawl/generation completed by the worker, and its workspace reloaded. Preview
deployment origins are not trusted for session exchange. Add exact origins to
`FRONTEND_ORIGINS` before using previews or a custom domain.

Verified on September 25, 2026: 251 backend tests, two proxy tests, frontend
production build, public health endpoint, creation-key enforcement, secure
session exchange and restoration, anonymous access denial, SSE delivery, and
a complete live crawl plus model-generated draft for `https://example.com/`.
