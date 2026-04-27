# Deployment

Production target: Azure Web App for Containers in subscription `Azure subscription 1` (Kardinia tenant), region `australiaeast`. Custom domain `aimap.cliftonfamily.co` fronted by Azure-managed TLS.

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

# 1. Add the domain to the Web App.
az webapp config hostname add \
  --webapp-name "$APP" \
  --resource-group "$RG" \
  --hostname "$DOMAIN"

# 2. Point DNS (manual step in Cloudflare / your DNS provider):
#    CNAME aimap -> <APP>.azurewebsites.net
#    Cloudflare proxy off (orange cloud grey) so the SNI hits Azure directly,
#    OR use full-strict mode if you want CF in front.

# 3. Issue Azure-managed TLS cert.
az webapp config ssl create \
  --resource-group "$RG" \
  --name "$APP" \
  --hostname "$DOMAIN"

az webapp config ssl bind \
  --resource-group "$RG" \
  --name "$APP" \
  --certificate-thumbprint <thumbprint-from-previous-command> \
  --ssl-type SNI
```

## Smoke checks

```bash
curl -I https://aimap.cliftonfamily.co               # expect HTTP/2 200, valid cert
curl -fsS https://aimap.cliftonfamily.co/_stcore/health
gh workflow run weekly.yml -f limit=5
gh run watch
```

## Tearing it down (if you ever need to)

```bash
az group delete -n ai-sector-watch --yes --no-wait
```

That removes the Web App, the App Service plan, and the SSL cert in one shot. The OIDC app registration lives at the tenant level and survives; delete it separately if needed.
