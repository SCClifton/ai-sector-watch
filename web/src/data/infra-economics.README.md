# AI Infrastructure Economics Assumptions

The `/infrastructure` page is a client-side dashboard. It does not read
Supabase yet. All stack, workload, scenario, project, probability, and source
assumptions live in `web/src/data/infraEconomics.ts`.

## Formula

```text
annualized_capex =
  total_capex * capital_recovery_factor(cost_of_capital, useful_life)

annual_power_cost =
  it_power_kw * PUE * 8760 * electricity_price_per_kwh

annual_total_cost =
  annualized_capex + annual_power_cost + annual_operating_cost

useful_tokens_per_year =
  tokens_per_second * seconds_per_year * utilization * goodput

cost_per_1m_tokens =
  annual_total_cost / useful_tokens_per_year * 1,000,000
```

`total_capex` includes system capex, network and storage uplift, and facility
capex allocated by stack IT power draw. The model treats stack prices,
throughput, MW allocations, utilization, and goodput as estimates unless a
source explicitly discloses them.

## Updating Stack Assumptions

Edit `STACK_PRESETS` in `infraEconomics.ts`.

Each stack has min, mode, and max distributions for:

- system capex
- network and storage uplift
- facility capex per MW
- IT power draw
- PUE
- electricity price
- useful life
- cost of capital
- operating and support cost
- utilization
- goodput
- full-load tokens/sec

The browser Monte Carlo uses triangular sampling from those distributions.
Percent fields are stored as decimals: use `0.65` for 65%.

## Adding A Project

Add a `DataCenterProject` entry to `DATA_CENTER_PROJECTS`.

Required fields include company, project name, location, announced capex,
disclosed or estimated MW, expected online year, full ramp year, ownership
model, counterparties, likely stack, source links, confidence score, and
probability evidence.

Use source labels consistently:

- `Company disclosed fact`
- `Public third-party report`
- `Analyst assumption`
- `User-editable estimate`

Do not copy paid or proprietary model values into this file. Public
SemiAnalysis material can be used for framing, but proprietary numbers must
stay out unless the maintainer explicitly provides a licensed data extract.

## Validation

Run:

```bash
npm run validate:infra
npm run lint
npm run build
```

The validation script checks basic model invariants and verifies that the public
source references used by stacks and projects exist in the source table.
