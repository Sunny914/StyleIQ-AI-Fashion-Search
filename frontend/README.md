# ProductIQ storefront

Next.js App Router interface for the existing ProductIQ search and recommendation API. The browser does not implement retrieval. It calls the FastAPI service and loads card details from the product route.

## What the API actually returns

Search results are `product_id` and `rank`. Recommendations add `recommendation_score`, which this UI does not display. Product detail returns brand, description, image URL, product URL, category gender, and product type. There is no separate title and no public price field, so cards use the description as the title and omit price.

Display cards are loaded with at most four product requests in flight, and the search page asks for at most 12 results.

## Setup

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env.local
npm run dev
```

Open `http://localhost:3000`.

`NEXT_PUBLIC_PRODUCTIQ_API_URL` is the only frontend setting. Point it at the published Compose API, for example `http://localhost:8010` when Compose is mapped to port 8010. Do not put secrets in this variable. If it is unset, the app uses `http://localhost:8000`, which is the Compose default.

## Connect to Docker Compose

Start the API and load the labeled fixture (not the 367,172-row catalog):

```bash
docker compose up -d postgres
docker compose --profile load run --rm catalog-load
docker compose up -d productiq-api
```

The browser calls the API directly. CORS allows `http://localhost:3000` and `http://127.0.0.1:3000` when `APP_ENV=development`. For any other origin, set `PRODUCTIQ_CORS_ALLOWED_ORIGINS` on the API. Leave `PRODUCTIQ_CORS_ALLOW_CREDENTIALS` off.

The header status line uses `/api/v1/health` and `/api/v1/ready`. A healthy process is not the full catalog. Fixture mode is labeled as a demo catalog.

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Development server |
| `npm run lint` | ESLint |
| `npm run typecheck` | TypeScript |
| `npm test` | Vitest |
| `npm run build` | Production build |
| `npm start` | Serve the production build |

Build-time `NEXT_PUBLIC_*` values are inlined. Set `.env.local` before `npm run build` if the production bundle should call a non-default API origin.

## Scope

No accounts, cart, checkout, or a second search engine. The three-row Compose fixture is enough to exercise search, product detail, and similar pieces.
