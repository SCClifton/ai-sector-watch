# Deployment

Production serves the Next.js dashboard from `web/` as a containerised app.
The legacy Streamlit dashboard under `dashboard/` is retained during migration
but is not the production entry point.

This file is public-safe. Keep tenant identifiers, subscription IDs, private
DNS notes, exact secret paths, and incident details out of the repository.

## Production Shape

```text
GitHub Actions
     |
     | build container
     v
GHCR image
     |
     | deploy
     v
Azure Web App for Containers
     |
     v
https://aimap.cliftonfamily.co
```

## Deployment Workflow

`.github/workflows/deploy.yml` runs on:

- manual dispatch
- pushes to `main` that touch `web/**`, `Dockerfile`, or the deploy workflow

The workflow:

1. Builds the Docker image from the repository root.
2. Pushes `:latest` and `:<sha>` tags to GHCR.
3. Authenticates to Azure with GitHub OIDC.
4. Deploys the SHA-tagged image to the existing Web App.

## Runtime Configuration

Required app settings:

- `SUPABASE_DB_URL`
- `ADMIN_PASSWORD`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- `ANTHROPIC_BUDGET_USD_PER_RUN`

Do not commit values. Store them in the production secret manager and GitHub
Actions secrets as appropriate.

## Port Contract

Azure App Service routes traffic to the port named by `WEBSITES_PORT`. Azure
does not inject that value into the container.

The Dockerfile therefore pins:

```text
PORT=8000
EXPOSE 8000
```

If the App Service port setting changes, update the Dockerfile in the same PR.

## Health Checks

Smoke checks after deployment:

```bash
curl -fsS https://aimap.cliftonfamily.co/api/health
curl -I https://aimap.cliftonfamily.co
```

Browser smoke:

- `/`
- `/map`
- `/companies`
- `/news`
- `/about`
- `/admin`

For `/admin`, verify auth gating and queue rendering without promoting or
rejecting a real record unless that is the purpose of the change.

## Rollback

Prefer rollback by immutable SHA tag:

```bash
az webapp config container set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$APP_NAME" \
  --container-image-name "$IMAGE_TAG"
```

Use a known-good SHA from the deploy history. Floating rollback tags are
acceptable only when they have been created deliberately and documented in the
private operator notes.

## Infrastructure Changes

Ask before:

- provisioning Azure resources
- changing DNS
- changing custom domain or TLS settings
- creating or rotating production secrets
- changing GitHub OIDC permissions
- running destructive database operations

Open a PR or issue comment before touching shared remote state so other agents
and operators can see the in-flight change.
