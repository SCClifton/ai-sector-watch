"use client";

import { useMemo, useState } from "react";
import { ArrowUpRight, Calculator, Database, Gauge, LineChart, RotateCcw } from "lucide-react";

import {
  DATA_CENTER_PROJECTS,
  DEFAULT_PROBABILITY_WEIGHTS,
  INFRA_SOURCES,
  SCENARIO_PRESETS,
  STACK_PRESETS,
  WORKLOAD_PRESETS,
} from "@/data/infraEconomics";
import {
  aggregateForecasts,
  assumptionLabel,
  calculateCostBreakdown,
  cloneAssumptions,
  compareStacks,
  projectForecast,
  runMonteCarlo,
  scoreCompletionProbability,
  sensitivityRows,
  stackAssumptionKeys,
  type DataCenterProject,
  type Distribution,
  type ProbabilityWeights,
  type ScenarioPreset,
  type StackAssumptions,
  type StackPreset,
} from "@/lib/infra-economics";
import { cn } from "@/lib/cn";

const SOURCE_BY_ID = new Map(INFRA_SOURCES.map((source) => [source.id, source]));

export function InfraEconomicsDashboard() {
  const [selectedStackId, setSelectedStackId] = useState(STACK_PRESETS[0].id);
  const [selectedWorkloadId, setSelectedWorkloadId] = useState(WORKLOAD_PRESETS[1].id);
  const [selectedScenarioId, setSelectedScenarioId] = useState(SCENARIO_PRESETS[0].id);
  const [assumptions, setAssumptions] = useState<StackAssumptions>(
    cloneAssumptions(STACK_PRESETS[0].assumptions),
  );
  const [probabilityWeights, setProbabilityWeights] = useState<ProbabilityWeights>({
    ...DEFAULT_PROBABILITY_WEIGHTS,
  });

  const selectedStack =
    STACK_PRESETS.find((stack) => stack.id === selectedStackId) ?? STACK_PRESETS[0];
  const selectedWorkload =
    WORKLOAD_PRESETS.find((workload) => workload.id === selectedWorkloadId) ??
    WORKLOAD_PRESETS[0];
  const selectedScenario =
    SCENARIO_PRESETS.find((scenario) => scenario.id === selectedScenarioId) ??
    SCENARIO_PRESETS[0];

  const monteCarlo = useMemo(
    () => runMonteCarlo(assumptions, selectedWorkload, 1800, selectedStack.id.length * 997),
    [assumptions, selectedStack.id.length, selectedWorkload],
  );
  const stackComparison = useMemo(
    () => compareStacks(STACK_PRESETS, selectedWorkload),
    [selectedWorkload],
  );
  const projectRows = useMemo(
    () =>
      DATA_CENTER_PROJECTS.map((project) => {
        const stack = STACK_PRESETS.find((item) => item.id === project.likelyStackId) ?? STACK_PRESETS[0];
        const forecast = projectForecast(project, stack, selectedWorkload, selectedScenario);
        const onlineYear = forecast.find((year) => year.mwOnline > 0);
        return {
          project,
          stack,
          forecast,
          completionProbability: scoreCompletionProbability(
            project,
            probabilityWeights,
            selectedScenario,
          ),
          onlineCostPer1M: onlineYear?.costPer1MTokens ?? 0,
        };
      }),
    [probabilityWeights, selectedScenario, selectedWorkload],
  );
  const aggregateRows = useMemo(
    () =>
      aggregateForecasts(
        projectRows.map((row) => ({ project: row.project, years: row.forecast })),
      ),
    [projectRows],
  );
  const selectedSensitivity = useMemo(
    () => sensitivityRows(assumptions, selectedWorkload),
    [assumptions, selectedWorkload],
  );

  return (
    <section className="mx-auto w-full max-w-[1400px] px-4 py-8 sm:px-5 sm:py-10">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-text-subtle">
            Infrastructure economics
          </div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-text sm:text-4xl">
            AI token cost dashboard
          </h1>
          <p className="mt-2 max-w-3xl text-[14px] leading-relaxed text-text-muted">
            Cost per token equals all-in annual stack cost divided by useful annual
            tokens. Adjust capex, power, utilization, goodput, and throughput to see how
            AI compute economics move.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 text-[12px] sm:flex">
          <Selector
            label="Stack"
            value={selectedStackId}
            options={STACK_PRESETS.map((stack) => ({ value: stack.id, label: stack.label }))}
            onChange={(nextStackId) => {
              const nextStack =
                STACK_PRESETS.find((stack) => stack.id === nextStackId) ?? STACK_PRESETS[0];
              setSelectedStackId(nextStackId);
              setAssumptions(cloneAssumptions(nextStack.assumptions));
            }}
          />
          <Selector
            label="Workload"
            value={selectedWorkloadId}
            options={WORKLOAD_PRESETS.map((workload) => ({
              value: workload.id,
              label: workload.label,
            }))}
            onChange={setSelectedWorkloadId}
          />
        </div>
      </div>

      <FirstPrinciples />

      <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <section className="rounded-lg border border-border bg-surface/50 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <SectionHeading
                icon={<Calculator className="h-4 w-4" />}
                eyebrow="Diligence question"
                title="What does this stack cost per 1M useful tokens?"
                body={`${selectedWorkload.label}: ${selectedWorkload.description}`}
              />
              <button
                type="button"
                onClick={() => setAssumptions(cloneAssumptions(selectedStack.assumptions))}
                className="inline-flex min-h-10 items-center gap-1.5 rounded-md border border-border bg-surface px-3 text-[12px] font-medium text-text-muted transition-colors hover:border-accent hover:text-accent"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Reset stack assumptions
              </button>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-4">
              <Metric label="P10 cost / 1M" value={formatCurrency(monteCarlo.p10.costPer1MTokens)} />
              <Metric label="P50 cost / 1M" value={formatCurrency(monteCarlo.p50.costPer1MTokens)} accent />
              <Metric label="P90 cost / 1M" value={formatCurrency(monteCarlo.p90.costPer1MTokens)} />
              <Metric
                label="Annual useful tokens"
                value={formatTokens(monteCarlo.p50.usefulTokensPerYear)}
              />
            </div>

            <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
              <div className="rounded-md border border-border bg-bg/30 p-3">
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
                  P50 token split
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <Metric
                    compact
                    label="Input tokens / 1M"
                    value={formatCurrency(monteCarlo.p50.inputCostPer1M)}
                  />
                  <Metric
                    compact
                    label="Output tokens / 1M"
                    value={formatCurrency(monteCarlo.p50.outputCostPer1M)}
                  />
                </div>
                <p className="mt-3 text-[12px] leading-relaxed text-text-subtle">
                  Output tokens are weighted higher because decoding consumes scarce
                  accelerator time and memory bandwidth. The multiplier is workload-specific.
                </p>
              </div>
              <CostDriverMix
                capital={monteCarlo.p50.capitalShare}
                power={monteCarlo.p50.powerShare}
                operations={monteCarlo.p50.operationsShare}
              />
            </div>
          </section>

          <AssumptionEditor assumptions={assumptions} onChange={setAssumptions} />

          <StackComparison rows={stackComparison} />
        </div>

        <aside className="space-y-4">
          <section className="rounded-lg border border-border bg-surface/50 p-4">
            <SectionHeading
              icon={<Gauge className="h-4 w-4" />}
              eyebrow="Operating leverage"
              title="Sensitivity to utilization and goodput"
              body="Same stack, same workload. Only utilization and useful-token efficiency move."
            />
            <div className="mt-4 space-y-2">
              {selectedSensitivity.map((row) => (
                <div key={row.label} className="rounded-md border border-border bg-bg/30 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[12px] font-medium text-text">{row.label}</span>
                    <span className="font-mono text-[13px] text-accent">
                      {formatCurrency(row.costPer1M)}
                    </span>
                  </div>
                  <div className="mt-2 text-[11px] text-text-subtle">
                    Utilization {formatPercent(row.utilization)}, goodput {formatPercent(row.goodput)}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-border bg-surface/50 p-4">
            <SectionHeading
              icon={<Database className="h-4 w-4" />}
              eyebrow="Selected stack"
              title={selectedStack.label}
              body={selectedStack.platformFamily}
            />
            <SourceLinks sourceIds={selectedStack.sourceIds} />
          </section>

          <section className="rounded-lg border border-border bg-surface/50 p-4">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
              Formula
            </div>
            <div className="mt-3 space-y-2 font-mono text-[11px] leading-relaxed text-text-muted">
              <p>annualized_capex = total_capex * CRF(rate, life)</p>
              <p>power_cost = kW * PUE * 8760 * $/kWh</p>
              <p>tokens = tok/sec * seconds * utilization * goodput</p>
              <p>cost_per_1M = annual_cost / tokens * 1,000,000</p>
            </div>
          </section>
        </aside>
      </div>

      <ProjectScenarioDashboard
        scenario={selectedScenario}
        scenarioId={selectedScenarioId}
        onScenarioChange={setSelectedScenarioId}
        rows={projectRows}
        aggregateRows={aggregateRows}
        weights={probabilityWeights}
        onWeightsChange={setProbabilityWeights}
      />

      <SourcesPanel />
    </section>
  );
}

function FirstPrinciples() {
  const items = [
    {
      label: "Capex",
      body: "Cash spent upfront on racks, accelerators, networking, storage, power, and cooling infrastructure.",
    },
    {
      label: "Depreciation",
      body: "Accounting spreads that upfront spend through earnings over the asset life.",
    },
    {
      label: "Free cash flow",
      body: "Free cash flow feels capex immediately because the cash leaves before tokens are sold.",
    },
    {
      label: "Useful compute",
      body: "Token economics depend on annualized capex, power cost, utilization, goodput, throughput, and workload mix.",
    },
    {
      label: "Data centers",
      body: "An announcement matters only when it becomes powered, cooled, networked, commissioned compute.",
    },
  ];
  return (
    <div className="mt-6 grid grid-cols-1 gap-2 md:grid-cols-5">
      {items.map((item) => (
        <div key={item.label} className="rounded-md border border-border bg-surface/50 p-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
            {item.label}
          </div>
          <p className="mt-2 text-[12px] leading-relaxed text-text-muted">{item.body}</p>
        </div>
      ))}
    </div>
  );
}

function AssumptionEditor({
  assumptions,
  onChange,
}: {
  assumptions: StackAssumptions;
  onChange: (next: StackAssumptions) => void;
}) {
  const update = (key: keyof StackAssumptions, field: keyof Distribution, value: number) => {
    onChange({
      ...assumptions,
      [key]: {
        ...assumptions[key],
        [field]: value,
      },
    });
  };

  return (
    <section className="rounded-lg border border-border bg-surface/50 p-4">
      <SectionHeading
        icon={<LineChart className="h-4 w-4" />}
        eyebrow="Editable distributions"
        title="What assumptions drive the simulation?"
        body="Min, mode, and max use triangular sampling. Percent fields are stored as decimals."
      />
      <div className="aisw-scroll mt-4 overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[760px] text-[12px]">
          <thead className="border-b border-border bg-bg/40 text-text-subtle">
            <tr className="text-left">
              <th className="px-3 py-2 font-medium">Variable</th>
              <th className="px-3 py-2 font-medium">Min</th>
              <th className="px-3 py-2 font-medium">Mode</th>
              <th className="px-3 py-2 font-medium">Max</th>
              <th className="px-3 py-2 font-medium">Unit</th>
              <th className="px-3 py-2 font-medium">Label</th>
            </tr>
          </thead>
          <tbody>
            {stackAssumptionKeys().map((key) => {
              const distribution = assumptions[key];
              return (
                <tr key={key} className="border-b border-border last:border-0">
                  <td className="px-3 py-2 font-medium text-text">{assumptionLabel(key)}</td>
                  {(["min", "mode", "max"] as const).map((field) => (
                    <td key={field} className="px-3 py-2">
                      <input
                        type="number"
                        value={distribution[field]}
                        step={inputStep(distribution)}
                        onChange={(event) => update(key, field, Number(event.target.value))}
                        className="h-9 w-28 rounded-md border border-border bg-bg px-2 font-mono text-[12px] text-text outline-none focus:border-accent"
                      />
                    </td>
                  ))}
                  <td className="px-3 py-2 text-text-muted">{distribution.unit}</td>
                  <td className="px-3 py-2 text-text-subtle">{distribution.sourceType}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function StackComparison({
  rows,
}: {
  rows: { stack: StackPreset; breakdown: ReturnType<typeof calculateCostBreakdown> }[];
}) {
  const maxCost = Math.max(...rows.map((row) => row.breakdown.costPer1MTokens));
  return (
    <section className="rounded-lg border border-border bg-surface/50 p-4">
      <SectionHeading
        icon={<Gauge className="h-4 w-4" />}
        eyebrow="Cross-stack comparison"
        title="Which platform is cheapest under the same workload?"
        body="Uses each stack preset mode value and the selected workload mix."
      />
      <div className="mt-4 space-y-2">
        {rows.map((row) => {
          const width = (row.breakdown.costPer1MTokens / maxCost) * 100;
          return (
            <div key={row.stack.id} className="grid grid-cols-[220px_minmax(0,1fr)_90px] items-center gap-3 text-[12px]">
              <div className="truncate font-medium text-text">{row.stack.label}</div>
              <div className="h-7 overflow-hidden rounded-md border border-border bg-bg">
                <div
                  className="h-full bg-accent/70"
                  style={{ width: `${Math.max(3, width)}%` }}
                  aria-label={`${row.stack.label} cost bar`}
                />
              </div>
              <div className="text-right font-mono text-text-muted">
                {formatCurrency(row.breakdown.costPer1MTokens)}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ProjectScenarioDashboard({
  scenario,
  scenarioId,
  onScenarioChange,
  rows,
  aggregateRows,
  weights,
  onWeightsChange,
}: {
  scenario: ScenarioPreset;
  scenarioId: string;
  onScenarioChange: (id: string) => void;
  rows: {
    project: DataCenterProject;
    stack: StackPreset;
    forecast: ReturnType<typeof projectForecast>;
    completionProbability: number;
    onlineCostPer1M: number;
  }[];
  aggregateRows: ReturnType<typeof aggregateForecasts>;
  weights: ProbabilityWeights;
  onWeightsChange: (next: ProbabilityWeights) => void;
}) {
  return (
    <section className="mt-8 rounded-lg border border-border bg-surface/50 p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <SectionHeading
          icon={<Database className="h-4 w-4" />}
          eyebrow="Project scenarios"
          title="Which public data-center announcements could become token capacity?"
          body="The table links public project disclosures to expected powered capacity, likely stack choice, probability, and estimated cost per 1M tokens once online."
        />
        <div className="flex flex-wrap gap-1.5">
          {SCENARIO_PRESETS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onScenarioChange(item.id)}
              className={cn(
                "min-h-9 rounded-md border px-2.5 text-[12px] font-medium transition-colors",
                scenarioId === item.id
                  ? "border-accent bg-accent-soft text-accent"
                  : "border-border bg-bg text-text-muted hover:border-border-strong hover:text-text",
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <p className="mt-3 max-w-4xl text-[12px] leading-relaxed text-text-subtle">
        Current scenario: {scenario.description}
      </p>

      <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_330px]">
        <div className="aisw-scroll overflow-x-auto rounded-md border border-border">
          <table className="w-full min-w-[1280px] text-[12px]">
            <thead className="border-b border-border bg-bg/40 text-text-subtle">
              <tr className="text-left">
                <th className="px-3 py-2 font-medium">Company</th>
                <th className="px-3 py-2 font-medium">Project</th>
                <th className="px-3 py-2 font-medium">Location</th>
                <th className="px-3 py-2 font-medium">Capex</th>
                <th className="px-3 py-2 font-medium">MW / GW</th>
                <th className="px-3 py-2 font-medium">Online</th>
                <th className="px-3 py-2 font-medium">Ownership</th>
                <th className="px-3 py-2 font-medium">Counterparties</th>
                <th className="px-3 py-2 font-medium">Likely stack</th>
                <th className="px-3 py-2 font-medium">Confidence</th>
                <th className="px-3 py-2 font-medium">Completion</th>
                <th className="px-3 py-2 font-medium">Delay risk</th>
                <th className="px-3 py-2 font-medium">Cost / 1M</th>
                <th className="px-3 py-2 font-medium">Sources</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.project.id} className="border-b border-border last:border-0 align-top">
                  <td className="px-3 py-3 font-medium text-text">{row.project.company}</td>
                  <td className="px-3 py-3 text-text">{row.project.projectName}</td>
                  <td className="px-3 py-3 text-text-muted">{row.project.location}</td>
                  <td className="px-3 py-3 font-mono text-text-muted">
                    ${row.project.announcedCapexB.toFixed(1)}B
                  </td>
                  <td className="px-3 py-3 font-mono text-text-muted">
                    {row.project.disclosedMw >= 1000
                      ? `${(row.project.disclosedMw / 1000).toFixed(1)} GW`
                      : `${row.project.disclosedMw.toFixed(0)} MW`}
                    <div className="mt-1 text-[10px] text-text-subtle">{row.project.mwSourceType}</div>
                  </td>
                  <td className="px-3 py-3 font-mono text-text-muted">
                    {row.project.expectedOnlineYear + scenario.delayYears}
                  </td>
                  <td className="px-3 py-3 text-text-muted">{row.project.ownershipModel}</td>
                  <td className="px-3 py-3 text-text-muted">{row.project.counterparties.join(", ")}</td>
                  <td className="px-3 py-3 text-text-muted">{row.stack.label}</td>
                  <td className="px-3 py-3 font-mono text-text-muted">
                    {formatPercent(row.project.confidenceScore)}
                  </td>
                  <td className="px-3 py-3 font-mono text-accent">
                    {formatPercent(row.completionProbability)}
                  </td>
                  <td className="px-3 py-3 font-mono text-text-muted">
                    {formatPercent(1 - row.completionProbability)}
                  </td>
                  <td className="px-3 py-3 font-mono text-text-muted">
                    {row.onlineCostPer1M > 0 ? formatCurrency(row.onlineCostPer1M) : "-"}
                  </td>
                  <td className="px-3 py-3">
                    <SourceLinks compact sourceIds={row.project.sourceIds} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <ProbabilityEditor weights={weights} onChange={onWeightsChange} />
      </div>

      <ForecastTables rows={rows} aggregateRows={aggregateRows} />
    </section>
  );
}

function ProbabilityEditor({
  weights,
  onChange,
}: {
  weights: ProbabilityWeights;
  onChange: (next: ProbabilityWeights) => void;
}) {
  const labels: Record<keyof ProbabilityWeights, string> = {
    siteEvidence: "Site evidence",
    constructionEvidence: "Named contractor evidence",
    powerEvidence: "Utility or power agreement",
    financingEvidence: "Financing, JV, or lease",
    chipCustomerEvidence: "Chip or customer anchor",
    regulatoryRiskPenalty: "Regulatory risk penalty",
    negativeEvidencePenalty: "Negative evidence penalty",
  };
  return (
    <div className="rounded-md border border-border bg-bg/30 p-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
        Transparent probability model
      </div>
      <p className="mt-2 text-[12px] leading-relaxed text-text-muted">
        Completion probability is weighted positive evidence minus risk penalties. Every
        weight is editable.
      </p>
      <div className="mt-3 space-y-2">
        {(Object.keys(weights) as (keyof ProbabilityWeights)[]).map((key) => (
          <label key={key} className="grid grid-cols-[minmax(0,1fr)_78px] items-center gap-2 text-[12px]">
            <span className="text-text-muted">{labels[key]}</span>
            <input
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={weights[key]}
              onChange={(event) => onChange({ ...weights, [key]: Number(event.target.value) })}
              className="h-9 rounded-md border border-border bg-bg px-2 font-mono text-text outline-none focus:border-accent"
            />
          </label>
        ))}
      </div>
    </div>
  );
}

function ForecastTables({
  rows,
  aggregateRows,
}: {
  rows: { project: DataCenterProject; forecast: ReturnType<typeof projectForecast> }[];
  aggregateRows: ReturnType<typeof aggregateForecasts>;
}) {
  const years = rows[0]?.forecast.map((item) => item.year) ?? [];
  return (
    <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
      <div className="rounded-md border border-border bg-bg/30 p-3">
        <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
          Year-by-year project forecast
        </div>
        <div className="aisw-scroll mt-3 overflow-x-auto">
          <table className="w-full min-w-[760px] text-[12px]">
            <thead className="border-b border-border text-text-subtle">
              <tr className="text-left">
                <th className="px-2 py-2 font-medium">Project</th>
                <th className="px-2 py-2 font-medium">Year</th>
                <th className="px-2 py-2 font-medium">MW</th>
                <th className="px-2 py-2 font-medium">Stacks</th>
                <th className="px-2 py-2 font-medium">Tokens</th>
                <th className="px-2 py-2 font-medium">Capex</th>
                <th className="px-2 py-2 font-medium">Power</th>
                <th className="px-2 py-2 font-medium">Ops</th>
                <th className="px-2 py-2 font-medium">Cost</th>
              </tr>
            </thead>
            <tbody>
              {rows.flatMap((row) =>
                row.forecast
                  .filter((year) => year.mwOnline > 0)
                  .slice(0, 4)
                  .map((year) => (
                    <tr key={`${row.project.id}-${year.year}`} className="border-b border-border last:border-0">
                      <td className="px-2 py-2 text-text">{row.project.projectName}</td>
                      <td className="px-2 py-2 font-mono text-text-muted">{year.year}</td>
                      <td className="px-2 py-2 font-mono text-text-muted">{year.mwOnline.toFixed(0)}</td>
                      <td className="px-2 py-2 font-mono text-text-muted">{year.equivalentStacks.toFixed(0)}</td>
                      <td className="px-2 py-2 font-mono text-text-muted">{formatTokens(year.annualUsefulTokens)}</td>
                      <td className="px-2 py-2 font-mono text-text-muted">{formatCurrency(year.annualizedCapex, "compact")}</td>
                      <td className="px-2 py-2 font-mono text-text-muted">{formatCurrency(year.annualPowerCost, "compact")}</td>
                      <td className="px-2 py-2 font-mono text-text-muted">{formatCurrency(year.annualOperatingCost, "compact")}</td>
                      <td className="px-2 py-2 font-mono text-accent">{formatCurrency(year.costPer1MTokens)}</td>
                    </tr>
                  )),
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded-md border border-border bg-bg/30 p-3">
        <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
          Aggregate capacity by company
        </div>
        <div className="aisw-scroll mt-3 overflow-x-auto">
          <table className="w-full min-w-[620px] text-[12px]">
            <thead className="border-b border-border text-text-subtle">
              <tr className="text-left">
                <th className="px-2 py-2 font-medium">Company</th>
                {years.map((year) => (
                  <th key={year} className="px-2 py-2 text-right font-medium">
                    {year}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {aggregateRows.map((row) => (
                <tr key={row.company} className="border-b border-border last:border-0">
                  <td className="px-2 py-2 font-medium text-text">{row.company}</td>
                  {row.years.map((year) => (
                    <td key={`${row.company}-${year.year}`} className="px-2 py-2 text-right">
                      <div className="font-mono text-text-muted">{year.mwOnline.toFixed(0)} MW</div>
                      {year.costPer1MTokens > 0 && (
                        <div className="font-mono text-[11px] text-accent">
                          {formatCurrency(year.costPer1MTokens)}
                        </div>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function SourcesPanel() {
  return (
    <section className="mt-8 rounded-lg border border-border bg-surface/50 p-4">
      <SectionHeading
        icon={<ArrowUpRight className="h-4 w-4" />}
        eyebrow="Sources and data hygiene"
        title="What is fact, report, assumption, or user-editable estimate?"
        body="Only public sources are included. Stack prices, throughput, MW allocations, and operating ratios are estimates unless explicitly disclosed."
      />
      <div className="mt-4 grid grid-cols-1 gap-2 lg:grid-cols-2">
        {INFRA_SOURCES.map((source) => (
          <a
            key={source.id}
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-md border border-border bg-bg/30 p-3 transition-colors hover:border-accent"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-[13px] font-semibold text-text">{source.label}</div>
                <div className="mt-1 text-[11px] font-medium uppercase tracking-[0.12em] text-accent">
                  {source.sourceType}
                </div>
              </div>
              <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-text-muted" />
            </div>
            <p className="mt-2 text-[12px] leading-relaxed text-text-muted">{source.note}</p>
          </a>
        ))}
      </div>
    </section>
  );
}

function CostDriverMix({
  capital,
  power,
  operations,
}: {
  capital: number;
  power: number;
  operations: number;
}) {
  return (
    <div className="rounded-md border border-border bg-bg/30 p-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
        P50 cost-driver mix
      </div>
      <div className="mt-3 flex h-7 overflow-hidden rounded-md border border-border bg-bg">
        <div className="bg-accent" style={{ width: `${capital * 100}%` }} title="Capital" />
        <div className="bg-success" style={{ width: `${power * 100}%` }} title="Power" />
        <div className="bg-surface-3" style={{ width: `${operations * 100}%` }} title="Operations" />
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-[11px]">
        <Legend label="Capital" value={formatPercent(capital)} className="bg-accent" />
        <Legend label="Power" value={formatPercent(power)} className="bg-success" />
        <Legend label="Operations" value={formatPercent(operations)} className="bg-surface-3" />
      </div>
    </div>
  );
}

function Legend({ label, value, className }: { label: string; value: string; className: string }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-text-muted">
        <span className={cn("h-2 w-2 rounded-sm", className)} />
        {label}
      </div>
      <div className="mt-1 font-mono text-text">{value}</div>
    </div>
  );
}

function SourceLinks({ sourceIds, compact = false }: { sourceIds: string[]; compact?: boolean }) {
  return (
    <div className={cn("mt-3 flex flex-wrap gap-1.5", compact && "mt-0 max-w-[240px]")}>
      {sourceIds.map((sourceId) => {
        const source = SOURCE_BY_ID.get(sourceId);
        if (!source) return null;
        return (
          <a
            key={source.id}
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-7 items-center gap-1 rounded-md border border-border bg-bg px-2 text-[11px] font-medium text-text-muted transition-colors hover:border-accent hover:text-accent"
          >
            {source.label}
            <ArrowUpRight className="h-3 w-3" />
          </a>
        );
      })}
    </div>
  );
}

function SectionHeading({
  icon,
  eyebrow,
  title,
  body,
}: {
  icon: React.ReactNode;
  eyebrow: string;
  title: string;
  body?: string;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
        <span className="text-accent">{icon}</span>
        {eyebrow}
      </div>
      <h2 className="mt-1 text-lg font-semibold tracking-tight text-text">{title}</h2>
      {body && <p className="mt-1 max-w-3xl text-[12px] leading-relaxed text-text-muted">{body}</p>}
    </div>
  );
}

function Metric({
  label,
  value,
  accent = false,
  compact = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
  compact?: boolean;
}) {
  return (
    <div className={cn("rounded-md border border-border bg-bg/30 p-3", compact && "p-2.5")}>
      <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
        {label}
      </div>
      <div className={cn("mt-1 font-mono font-semibold tabular-nums", compact ? "text-[16px]" : "text-[22px]", accent ? "text-accent" : "text-text")}>
        {value}
      </div>
    </div>
  );
}

function Selector({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-1">
      <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 rounded-md border border-border bg-surface px-2.5 text-[12px] font-medium text-text outline-none focus:border-accent"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function inputStep(distribution: Distribution): number {
  if (distribution.unit.includes("%") || distribution.unit === "ratio" || distribution.unit.includes("$/kWh")) {
    return 0.01;
  }
  if (distribution.mode > 10000) return 1000;
  if (distribution.mode > 100) return 5;
  return 0.1;
}

function formatCurrency(value: number, mode: "normal" | "compact" = "normal"): string {
  if (!Number.isFinite(value)) return "-";
  if (mode === "compact") {
    if (Math.abs(value) >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
    if (Math.abs(value) >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
    if (Math.abs(value) >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  }
  if (value >= 100) return `$${value.toFixed(0)}`;
  if (value >= 10) return `$${value.toFixed(1)}`;
  return `$${value.toFixed(2)}`;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

function formatTokens(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "-";
  if (value >= 1e18) return `${(value / 1e18).toFixed(1)}E`;
  if (value >= 1e15) return `${(value / 1e15).toFixed(1)}P`;
  if (value >= 1e12) return `${(value / 1e12).toFixed(1)}T`;
  if (value >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  return value.toFixed(0);
}
