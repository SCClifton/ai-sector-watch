# Web Dashboard

Next.js dashboard for AI Sector Watch. This is the production public app served
at https://aimap.cliftonfamily.co.

## Stack

- Next.js 16 app router
- TypeScript
- Tailwind CSS v4
- MapLibre GL JS
- Supabase Postgres via server-side `postgres`

## Run Locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

Live data requires `SUPABASE_DB_URL` in the environment. Without it, routes that
read live data may return server-side errors or empty states.

## Checks

```bash
npm run build
npm run lint
```

## Main Routes

- `/` - public overview
- `/map` - interactive company map
- `/companies` - searchable company directory
- `/news` - recent public activity
- `/about` - scope and methodology
- `/admin` - password-gated review queue

## Notes

- Public pages must show only verified companies.
- Admin mutations must stay server-side and authenticated.
- Do not expose raw review artifacts, source extracts, or private operational
  details in UI copy.
