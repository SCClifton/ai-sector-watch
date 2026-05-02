export type SourceType =
  | "Company disclosed fact"
  | "Public third-party report"
  | "Analyst assumption"
  | "User-editable estimate";

export interface SourceRecord {
  id: string;
  label: string;
  url: string;
  sourceType: SourceType;
  note: string;
}

export interface Distribution {
  min: number;
  mode: number;
  max: number;
  unit: string;
  sourceType: SourceType;
}

export interface StackAssumptions {
  systemCapexM: Distribution;
  networkStorageUpliftPct: Distribution;
  facilityCapexPerMwM: Distribution;
  itPowerKw: Distribution;
  pue: Distribution;
  electricityPricePerKwh: Distribution;
  usefulLifeYears: Distribution;
  costOfCapitalPct: Distribution;
  operatingSupportPct: Distribution;
  utilizationPct: Distribution;
  goodputPct: Distribution;
  tokensPerSecond: Distribution;
}

export interface StackPreset {
  id: string;
  label: string;
  platformFamily: string;
  sourceIds: string[];
  assumptions: StackAssumptions;
}

export interface WorkloadPreset {
  id: string;
  label: string;
  description: string;
  inputShare: number;
  outputShare: number;
  outputCostMultiplier: number;
  throughputMultiplier: number;
  goodputMultiplier: number;
}

export interface ScenarioPreset {
  id: string;
  label: string;
  description: string;
  delayYears: number;
  capexMultiplier: number;
  powerPriceMultiplier: number;
  facilityCapexMultiplier: number;
  utilizationMultiplier: number;
  goodputMultiplier: number;
  throughputMultiplier: number;
  completionAdjustment: number;
  capacityRampMultiplier: number;
}

export interface ProbabilityWeights {
  siteEvidence: number;
  constructionEvidence: number;
  powerEvidence: number;
  financingEvidence: number;
  chipCustomerEvidence: number;
  regulatoryRiskPenalty: number;
  negativeEvidencePenalty: number;
}

export interface ProjectEvidence {
  siteEvidence: number;
  constructionEvidence: number;
  powerEvidence: number;
  financingEvidence: number;
  chipCustomerEvidence: number;
  regulatoryRisk: number;
  negativeEvidence: number;
}

export interface DataCenterProject {
  id: string;
  company: "Microsoft" | "Alphabet / Google" | "Amazon / AWS" | "Meta";
  projectName: string;
  location: string;
  announcedCapexB: number;
  disclosedMw: number;
  mwSourceType: SourceType;
  expectedOnlineYear: number;
  fullRampYear: number;
  ownershipModel: "Owned" | "Leased" | "JV" | "Colo" | "Build-to-suit" | "JV / build-to-suit";
  counterparties: string[];
  likelyStackId: string;
  sourceIds: string[];
  confidenceScore: number;
  evidence: ProjectEvidence;
}

export interface CostBreakdown {
  totalCapex: number;
  annualizedCapex: number;
  annualPowerCost: number;
  annualOperatingCost: number;
  annualTotalCost: number;
  usefulTokensPerYear: number;
  rawTokensPerYear: number;
  costPer1MTokens: number;
  inputCostPer1M: number;
  outputCostPer1M: number;
  capitalShare: number;
  powerShare: number;
  operationsShare: number;
}

export interface MonteCarloResult {
  p10: CostBreakdown;
  p50: CostBreakdown;
  p90: CostBreakdown;
  samples: CostBreakdown[];
}

export interface ForecastYear {
  year: number;
  mwOnline: number;
  equivalentStacks: number;
  annualUsefulTokens: number;
  annualizedCapex: number;
  annualPowerCost: number;
  annualOperatingCost: number;
  costPer1MTokens: number;
  utilization: number;
  goodput: number;
}

const SECONDS_PER_YEAR = 365 * 24 * 60 * 60;

const ASSUMPTION_KEYS: (keyof StackAssumptions)[] = [
  "systemCapexM",
  "networkStorageUpliftPct",
  "facilityCapexPerMwM",
  "itPowerKw",
  "pue",
  "electricityPricePerKwh",
  "usefulLifeYears",
  "costOfCapitalPct",
  "operatingSupportPct",
  "utilizationPct",
  "goodputPct",
  "tokensPerSecond",
];

export function stackAssumptionKeys(): (keyof StackAssumptions)[] {
  return ASSUMPTION_KEYS;
}

export function cloneAssumptions(assumptions: StackAssumptions): StackAssumptions {
  return Object.fromEntries(
    ASSUMPTION_KEYS.map((key) => [key, { ...assumptions[key] }]),
  ) as unknown as StackAssumptions;
}

export function assumptionLabel(key: keyof StackAssumptions): string {
  const labels: Record<keyof StackAssumptions, string> = {
    systemCapexM: "System capex",
    networkStorageUpliftPct: "Network and storage uplift",
    facilityCapexPerMwM: "Facility capex per MW",
    itPowerKw: "IT power draw",
    pue: "PUE",
    electricityPricePerKwh: "Electricity price",
    usefulLifeYears: "Useful life",
    costOfCapitalPct: "Cost of capital",
    operatingSupportPct: "Operating and support cost",
    utilizationPct: "Utilization",
    goodputPct: "Goodput",
    tokensPerSecond: "Full-load tokens/sec",
  };
  return labels[key];
}

export function capitalRecoveryFactor(rate: number, years: number): number {
  if (years <= 0) return 0;
  if (rate === 0) return 1 / years;
  const growth = (1 + rate) ** years;
  return (rate * growth) / (growth - 1);
}

export function calculateCostBreakdown(
  assumptions: StackAssumptions,
  workload: WorkloadPreset,
  scenario?: ScenarioPreset,
): CostBreakdown {
  const modifier = scenario ?? neutralScenario();
  const systemCapex = assumptions.systemCapexM.mode * 1_000_000 * modifier.capexMultiplier;
  const networkStorageCapex =
    systemCapex * assumptions.networkStorageUpliftPct.mode * modifier.capexMultiplier;
  const itPowerKw = assumptions.itPowerKw.mode;
  const facilityCapex =
    (itPowerKw / 1000) *
    assumptions.facilityCapexPerMwM.mode *
    1_000_000 *
    modifier.facilityCapexMultiplier;
  const totalCapex = systemCapex + networkStorageCapex + facilityCapex;
  const crf = capitalRecoveryFactor(assumptions.costOfCapitalPct.mode, assumptions.usefulLifeYears.mode);
  const annualizedCapex = totalCapex * crf;
  const annualPowerCost =
    itPowerKw *
    assumptions.pue.mode *
    8760 *
    assumptions.electricityPricePerKwh.mode *
    modifier.powerPriceMultiplier;
  const annualOperatingCost = totalCapex * assumptions.operatingSupportPct.mode;
  const annualTotalCost = annualizedCapex + annualPowerCost + annualOperatingCost;
  const utilization = clamp(assumptions.utilizationPct.mode * modifier.utilizationMultiplier, 0, 0.98);
  const goodput = clamp(
    assumptions.goodputPct.mode * workload.goodputMultiplier * modifier.goodputMultiplier,
    0,
    0.98,
  );
  const tokensPerSecond =
    assumptions.tokensPerSecond.mode * workload.throughputMultiplier * modifier.throughputMultiplier;
  const rawTokensPerYear = tokensPerSecond * SECONDS_PER_YEAR * utilization;
  const usefulTokensPerYear = rawTokensPerYear * goodput;
  const costPer1MTokens = (annualTotalCost / usefulTokensPerYear) * 1_000_000;
  const inputWeight =
    workload.inputShare + workload.outputShare * workload.outputCostMultiplier;
  const inputCostPer1M = costPer1MTokens / inputWeight;
  const outputCostPer1M = inputCostPer1M * workload.outputCostMultiplier;

  return withCostShares({
    totalCapex,
    annualizedCapex,
    annualPowerCost,
    annualOperatingCost,
    annualTotalCost,
    usefulTokensPerYear,
    rawTokensPerYear,
    costPer1MTokens,
    inputCostPer1M,
    outputCostPer1M,
    capitalShare: 0,
    powerShare: 0,
    operationsShare: 0,
  });
}

export function runMonteCarlo(
  assumptions: StackAssumptions,
  workload: WorkloadPreset,
  iterations = 1600,
  seed = 42,
): MonteCarloResult {
  let randomState = seed;
  const nextRandom = () => {
    randomState = (randomState * 1664525 + 1013904223) >>> 0;
    return randomState / 2 ** 32;
  };

  const samples = Array.from({ length: iterations }, () => {
    const sampled = Object.fromEntries(
      ASSUMPTION_KEYS.map((key) => [
        key,
        {
          ...assumptions[key],
          mode: triangularSample(assumptions[key], nextRandom()),
        },
      ]),
    ) as unknown as StackAssumptions;
    return calculateCostBreakdown(sampled, workload);
  }).sort((a, b) => a.costPer1MTokens - b.costPer1MTokens);

  return {
    p10: samples[quantileIndex(samples.length, 0.1)],
    p50: samples[quantileIndex(samples.length, 0.5)],
    p90: samples[quantileIndex(samples.length, 0.9)],
    samples,
  };
}

export function compareStacks(
  stacks: StackPreset[],
  workload: WorkloadPreset,
): { stack: StackPreset; breakdown: CostBreakdown }[] {
  return stacks
    .map((stack) => ({
      stack,
      breakdown: calculateCostBreakdown(stack.assumptions, workload),
    }))
    .sort((a, b) => a.breakdown.costPer1MTokens - b.breakdown.costPer1MTokens);
}

export function scoreCompletionProbability(
  project: DataCenterProject,
  weights: ProbabilityWeights,
  scenario?: ScenarioPreset,
): number {
  const positive =
    project.evidence.siteEvidence * weights.siteEvidence +
    project.evidence.constructionEvidence * weights.constructionEvidence +
    project.evidence.powerEvidence * weights.powerEvidence +
    project.evidence.financingEvidence * weights.financingEvidence +
    project.evidence.chipCustomerEvidence * weights.chipCustomerEvidence;
  const penalty =
    project.evidence.regulatoryRisk * weights.regulatoryRiskPenalty +
    project.evidence.negativeEvidence * weights.negativeEvidencePenalty;
  return clamp(positive - penalty + (scenario?.completionAdjustment ?? 0), 0.03, 0.98);
}

export function projectForecast(
  project: DataCenterProject,
  stack: StackPreset,
  workload: WorkloadPreset,
  scenario: ScenarioPreset,
  startYear = 2026,
  endYear = 2032,
): ForecastYear[] {
  const onlineYear = project.expectedOnlineYear + scenario.delayYears;
  const fullRampYear = Math.max(onlineYear, project.fullRampYear + scenario.delayYears);
  const base = calculateCostBreakdown(stack.assumptions, workload, scenario);
  const stackMw = stack.assumptions.itPowerKw.mode / 1000;
  const years: ForecastYear[] = [];

  for (let year = startYear; year <= endYear; year += 1) {
    const ramp = rampFraction(year, onlineYear, fullRampYear) * scenario.capacityRampMultiplier;
    const mwOnline = project.disclosedMw * ramp;
    const equivalentStacks = stackMw > 0 ? mwOnline / stackMw : 0;
    const annualUsefulTokens = base.usefulTokensPerYear * equivalentStacks;
    years.push({
      year,
      mwOnline,
      equivalentStacks,
      annualUsefulTokens,
      annualizedCapex: base.annualizedCapex * equivalentStacks,
      annualPowerCost: base.annualPowerCost * equivalentStacks,
      annualOperatingCost: base.annualOperatingCost * equivalentStacks,
      costPer1MTokens: ramp > 0 ? base.costPer1MTokens : 0,
      utilization: clamp(stack.assumptions.utilizationPct.mode * scenario.utilizationMultiplier, 0, 0.98),
      goodput: clamp(
        stack.assumptions.goodputPct.mode * workload.goodputMultiplier * scenario.goodputMultiplier,
        0,
        0.98,
      ),
    });
  }

  return years;
}

export function aggregateForecasts(
  forecasts: { project: DataCenterProject; years: ForecastYear[] }[],
): { company: DataCenterProject["company"]; years: ForecastYear[] }[] {
  const companyMap = new Map<DataCenterProject["company"], Map<number, ForecastYear>>();

  forecasts.forEach(({ project, years }) => {
    if (!companyMap.has(project.company)) companyMap.set(project.company, new Map());
    const byYear = companyMap.get(project.company);
    if (!byYear) return;
    years.forEach((year) => {
      const existing = byYear.get(year.year);
      if (!existing) {
        byYear.set(year.year, { ...year });
        return;
      }
      const annualTotal =
        existing.annualizedCapex +
        existing.annualPowerCost +
        existing.annualOperatingCost +
        year.annualizedCapex +
        year.annualPowerCost +
        year.annualOperatingCost;
      const annualTokens = existing.annualUsefulTokens + year.annualUsefulTokens;
      byYear.set(year.year, {
        year: year.year,
        mwOnline: existing.mwOnline + year.mwOnline,
        equivalentStacks: existing.equivalentStacks + year.equivalentStacks,
        annualUsefulTokens: annualTokens,
        annualizedCapex: existing.annualizedCapex + year.annualizedCapex,
        annualPowerCost: existing.annualPowerCost + year.annualPowerCost,
        annualOperatingCost: existing.annualOperatingCost + year.annualOperatingCost,
        costPer1MTokens: annualTokens > 0 ? (annualTotal / annualTokens) * 1_000_000 : 0,
        utilization: year.utilization,
        goodput: year.goodput,
      });
    });
  });

  return Array.from(companyMap.entries()).map(([company, byYear]) => ({
    company,
    years: Array.from(byYear.values()).sort((a, b) => a.year - b.year),
  }));
}

export function sensitivityRows(
  assumptions: StackAssumptions,
  workload: WorkloadPreset,
): { label: string; utilization: number; goodput: number; costPer1M: number }[] {
  const cases = [
    { label: "Low utilization, weak goodput", utilization: 0.45, goodput: 0.45 },
    { label: "Base operating case", utilization: assumptions.utilizationPct.mode, goodput: assumptions.goodputPct.mode },
    { label: "High utilization, strong goodput", utilization: 0.82, goodput: 0.78 },
  ];
  return cases.map((item) => {
    const adjusted = cloneAssumptions(assumptions);
    adjusted.utilizationPct.mode = item.utilization;
    adjusted.goodputPct.mode = item.goodput;
    return {
      ...item,
      costPer1M: calculateCostBreakdown(adjusted, workload).costPer1MTokens,
    };
  });
}

function neutralScenario(): ScenarioPreset {
  return {
    id: "neutral",
    label: "Neutral",
    description: "",
    delayYears: 0,
    capexMultiplier: 1,
    powerPriceMultiplier: 1,
    facilityCapexMultiplier: 1,
    utilizationMultiplier: 1,
    goodputMultiplier: 1,
    throughputMultiplier: 1,
    completionAdjustment: 0,
    capacityRampMultiplier: 1,
  };
}

function triangularSample(distribution: Distribution, random: number): number {
  const { min, mode, max } = distribution;
  if (max <= min) return mode;
  const c = (mode - min) / (max - min);
  if (random < c) return min + Math.sqrt(random * (max - min) * (mode - min));
  return max - Math.sqrt((1 - random) * (max - min) * (max - mode));
}

function quantileIndex(length: number, quantile: number): number {
  return Math.min(length - 1, Math.max(0, Math.floor((length - 1) * quantile)));
}

function withCostShares(result: CostBreakdown): CostBreakdown {
  return {
    ...result,
    capitalShare: result.annualizedCapex / result.annualTotalCost,
    powerShare: result.annualPowerCost / result.annualTotalCost,
    operationsShare: result.annualOperatingCost / result.annualTotalCost,
  };
}

function rampFraction(year: number, onlineYear: number, fullRampYear: number): number {
  if (year < onlineYear) return 0;
  if (year >= fullRampYear) return 1;
  const span = Math.max(1, fullRampYear - onlineYear);
  return clamp((year - onlineYear + 1) / (span + 1), 0, 1);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
