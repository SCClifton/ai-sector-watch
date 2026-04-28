# Deployment

Production target: Azure Web App for Containers in subscription `Azure subscription 1` (Kardinia tenant), region `australiaeast`. Custom domain `aimap.cliftonfamily.co` fronted by Azure-managed TLS.

**As of Phase 3 (issue #68):** the deployed container is the Next.js app under `web/`. The Streamlit code under `dashboard/` stays in the repo for one cooling-off release but is no longer deployed. The previous Streamlit image is preserved in GHCR at the tag `:streamlit-final` for rollback.

## Cutover from Streamlit to Next.js (Phase 3)

The merge of #68 to `main` triggers `deploy.yml`, which builds the new Next.js Dockerfile, pushes to GHCR with `:latest` and `:<sha>` tags, and deploys to the existing App Service. The container honours the `PORT` env var that Azure sets from `WEBSITES_PORT`, so the cutover does not require any port change.

### Manual steps before merge (one-time)

These run from your laptop with `az login` already active. They are optional but recommended.

```bash
RG=ai-sector-watch
APP=ai-sector-watch
IMAGE_BASE=ghcr.io/scclifton/ai-sector-watch/ai-sector-watch

# 1. Tag the current Streamlit image as :streamlit-final so we can roll back.
#    Get the digest of whatever :latest currently points at (this should be
#    the last green Streamlit deploy).
docker pull "$IMAGE_BASE:latest"
docker tag  "$IMAGE_BASE:latest" "$IMAGE_BASE:streamlit-final"
docker push "$IMAGE_BASE:streamlit-final"

# 2. (Optional) Update the App Service health-check path to /api/health.
#    The Next.js Dockerfile also serves /_stcore/health via a rewrite for
#    backward compatibility, so this can wait if Azure's health check is
#    still pointed at /_stcore/health.
az webapp config set \
  --resource-group "$RG" \
  --name "$APP" \
  --generic-configurations '{"healthCheckPath": "/api/health"}'

# 3. (Optional) Update WEBSITES_PORT to 3000. Not required: the new
#    container reads PORT from the env, so leaving WEBSITES_PORT=8000
#    just makes Next.js bind to 8000.
az webapp config appsettings set \
  --resource-group "$RG" \
  --name "$APP" \
  --settings WEBSITES_PORT=3000
```

### What happens on merge

1. Push to `main` matches `web/**` or `Dockerfile`. `deploy.yml` runs.
2. The job builds the multi-stage Next.js Dockerfile, pushes `:latest` and `:<sha>` to GHCR, and calls `azure/webapps-deploy@v3` against the same App Service.
3. App Service pulls the new image and restarts the container.
4. The container starts `node server.js` listening on `PORT` (`WEBSITES_PORT`'s value, default 3000).
5. Within ~60s `https://aimap.cliftonfamily.co` should serve the new app.

### Smoke checks after cutover

```bash
curl -fsS https://aimap.cliftonfamily.co/api/health   # {"ok":true,...}
curl -fsS https://aimap.cliftonfamily.co/_stcore/health  # ok (compat)
curl -I  https://aimap.cliftonfamily.co               # 200, valid cert
# Browser: load /, /map, /companies, /news, /about. Confirm the Next.js
# header / footer / dark theme. Hit /admin, sign in, confirm the queue
# loads (no real promote needed).
```

### Rollback

If anything goes wrong, redeploy `:streamlit-final`:

```bash
az webapp config container set \
  --resource-group ai-sector-watch \
  --name ai-sector-watch \
  --container-image-name ghcr.io/scclifton/ai-sector-watch/ai-sector-watch:streamlit-final
```

Or trigger the previous green deploy via `gh workflow run` on a Streamlit-era SHA. Watch logs:

```bash
az webapp log tail --resource-group ai-sector-watch --name ai-sector-watch
```

## One-time setup (Sam)

Run these from your laptop with `az login` already active.

```bash
RG=ai-sector-watch
LOC=australiaeast
PLAN=ai-sector-watch-plan
APP=ai-sector-watch
ACR_OR_GHCR=ghcr.io/SCClifton/ai-sector-watch/ai-sector-watch:latest

# 1. Resource group
az group create -n "$RG" -l "$LOC"

# 2. App Service plan (Linux, B1 is enough for v0)
az appservice plan create \
  --name "$PLAN" \
  --resource-group "$RG" \
  --is-linux \
  --sku B1

# 3. Web App for Containers (image pulled at deploy time by GH Actions)
az webapp create \
  --resource-group "$RG" \
  --plan "$PLAN" \
  --name "$APP" \
  --deployment-container-image-name "$ACR_OR_GHCR"

# 4. Tell the container what port to bind
az webapp config appsettings set \
  --resource-group "$RG" \
  --name "$APP" \
  --settings WEBSITES_PORT=8000

# Streamlit needs a persistent WebSocket connection for the browser session.
# Without this, health checks can pass while visitors see only the empty shell.
az webapp config set \
  --resource-group "$RG" \
  --name "$APP" \
  --web-sockets-enabled true

# 5. App settings (mirror from 1Password manually for v0)
ANTHROPIC_API_KEY=$(op read "op://Private/Anthropic API Key/credential")
SUPABASE_DB_URL=$(op read "op://Private/Supabase AI Sector Watch/connection_string")
ADMIN_PASSWORD=$(op read "op://Private/AI Sector Watch Admin/password")

az webapp config appsettings set \
  --resource-group "$RG" \
  --name "$APP" \
  --settings \
    ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
    SUPABASE_DB_URL="$SUPABASE_DB_URL" \
    ADMIN_PASSWORD="$ADMIN_PASSWORD" \
    ANTHROPIC_BUDGET_USD_PER_RUN=2 \
    ANTHROPIC_MODEL=claude-sonnet-4-6

# 6. Health check
az webapp show -g "$RG" -n "$APP" --query "defaultHostName" -o tsv
curl -I "https://$(az webapp show -g "$RG" -n "$APP" --query defaultHostName -o tsv)"
```

## OIDC federated credential for GitHub Actions

So `deploy.yml` can authenticate without a stored client secret:

```bash
APP_REG_NAME=ai-sector-watch-github
GH_REPO=SCClifton/ai-sector-watch

CLIENT_ID=$(az ad app create --display-name "$APP_REG_NAME" --query appId -o tsv)
SP_ID=$(az ad sp create --id "$CLIENT_ID" --query id -o tsv)

az role assignment create \
  --assignee "$SP_ID" \
  --role "Website Contributor" \
  --scope "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RG"

az ad app federated-credential create \
  --id "$CLIENT_ID" \
  --parameters '{
    "name": "github-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:'"$GH_REPO"':ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# Push these into GH repo secrets:
TENANT_ID=$(az account show --query tenantId -o tsv)
SUB_ID=$(az account show --query id -o tsv)

gh secret set AZURE_CLIENT_ID --body "$CLIENT_ID"
gh secret set AZURE_TENANT_ID --body "$TENANT_ID"
gh secret set AZURE_SUBSCRIPTION_ID --body "$SUB_ID"
```

## Custom domain + TLS

```bash
DOMAIN=aimap.cliftonfamily.co

# 1. Point DNS first (manual step in Cloudflare DNS for cliftonfamily.co):
#    CNAME aimap -> ai-sector-watch.azurewebsites.net
#    Cloudflare proxy MUST be OFF (grey cloud) for the SNI handshake during
#    Azure-managed cert issuance. Leave it off for v0.
#
#    Alternative for verification without DNS pointing yet: add a TXT record
#    asuid.aimap = <customDomainVerificationId>, then add the binding,
#    then add the CNAME. Get the verification id with:
#      az webapp show -g "$RG" -n "$APP" --query customDomainVerificationId -o tsv

# 2. Add the domain to the Web App (requires CNAME or asuid TXT in place).
az webapp config hostname add \
  --webapp-name "$APP" \
  --resource-group "$RG" \
  --hostname "$DOMAIN"

# 3. Issue Azure-managed TLS cert.
az webapp config ssl create \
  --resource-group "$RG" \
  --name "$APP" \
  --hostname "$DOMAIN"

# Capture the thumbprint from the previous command's output (or query it):
THUMBPRINT=$(az webapp config ssl list -g "$RG" \
  --query "[?subjectName=='$DOMAIN'] | [0].thumbprint" -o tsv)

az webapp config ssl bind \
  --resource-group "$RG" \
  --name "$APP" \
  --certificate-thumbprint "$THUMBPRINT" \
  --ssl-type SNI
```

## Smoke checks (post-cutover)

```bash
curl -I  https://aimap.cliftonfamily.co               # HTTP/2 200, valid cert
curl -fsS https://aimap.cliftonfamily.co/api/health   # {"ok":true,...}
# Browser smoke: open /, /map, /companies, /news, /about. Expect the
# Next.js header / dark theme. Hit /admin, sign in, confirm the queue
# loads (no real promote needed).
gh workflow run weekly.yml -f limit=5
gh run watch
```

## Tearing it down (if you ever need to)

```bash
az group delete -n ai-sector-watch --yes --no-wait
```

That removes the Web App, the App Service plan, and the SSL cert in one shot. The OIDC app registration lives at the tenant level and survives; delete it separately if needed.
