const infra = await import("../src/lib/infra-economics.ts");
const data = await import("../src/data/infraEconomics.ts");

const assumptions = {
  systemCapexM: dist(10, "$M per stack"),
  networkStorageUpliftPct: dist(0.2, "% of system capex"),
  facilityCapexPerMwM: dist(20, "$M per MW"),
  itPowerKw: dist(100, "kW"),
  pue: dist(1.2, "ratio"),
  electricityPricePerKwh: dist(0.1, "$/kWh"),
  usefulLifeYears: dist(4, "years"),
  costOfCapitalPct: dist(0.1, "%"),
  operatingSupportPct: dist(0.08, "% of capex/year"),
  utilizationPct: dist(0.5, "%"),
  goodputPct: dist(0.5, "%"),
  tokensPerSecond: dist(1000, "tokens/sec"),
};

const workload = {
  id: "validation",
  label: "Validation",
  description: "Deterministic validation workload",
  inputShare: 0.5,
  outputShare: 0.5,
  outputCostMultiplier: 2,
  throughputMultiplier: 1,
  goodputMultiplier: 1,
};

const result = infra.calculateCostBreakdown(assumptions, workload);
const expectedSystemCapex = 10_000_000;
const expectedNetworkCapex = 2_000_000;
const expectedFacilityCapex = 2_000_000;
const expectedCapex = expectedSystemCapex + expectedNetworkCapex + expectedFacilityCapex;
const expectedCrf = infra.capitalRecoveryFactor(0.1, 4);
const expectedAnnualPower = 100 * 1.2 * 8760 * 0.1;
// Operating cost is applied to system + network (IT) capex only; facility ops is
// embedded in the facility capex and PUE-inflated power line.
const expectedAnnualOps = (expectedSystemCapex + expectedNetworkCapex) * 0.08;
const expectedAnnualCost = expectedCapex * expectedCrf + expectedAnnualPower + expectedAnnualOps;
const expectedTokens = 1000 * 365 * 24 * 60 * 60 * 0.5 * 0.5;
const expectedCost = (expectedAnnualCost / expectedTokens) * 1_000_000;

assertClose(result.totalCapex, expectedCapex, "total capex");
assertClose(result.annualPowerCost, expectedAnnualPower, "annual power cost");
assertClose(result.annualOperatingCost, expectedAnnualOps, "annual operating cost");
assertClose(result.costPer1MTokens, expectedCost, "cost per 1M tokens");
assertClose(result.inputCostPer1M, expectedCost / 1.5, "input token cost");
assertClose(result.outputCostPer1M, (expectedCost / 1.5) * 2, "output token cost");

const monteCarlo = infra.runMonteCarlo(assumptions, workload, 100, 7);
if (!(monteCarlo.p10.costPer1MTokens <= monteCarlo.p50.costPer1MTokens)) {
  throw new Error("Monte Carlo P10 must be <= P50");
}
if (!(monteCarlo.p50.costPer1MTokens <= monteCarlo.p90.costPer1MTokens)) {
  throw new Error("Monte Carlo P50 must be <= P90");
}

validatePresetCoverage();
validateSanityBands();

console.log("infra economics validation passed");

function dist(mode, unit) {
  return {
    min: mode,
    mode,
    max: mode,
    unit,
    sourceType: "Analyst assumption",
  };
}

function assertClose(actual, expected, label) {
  const delta = Math.abs(actual - expected);
  const tolerance = Math.max(1e-6, Math.abs(expected) * 1e-9);
  if (delta > tolerance) {
    throw new Error(`${label}: expected ${expected}, got ${actual}`);
  }
}

function validatePresetCoverage() {
  const sourceIds = new Set(data.INFRA_SOURCES.map((source) => source.id));

  for (const stack of data.STACK_PRESETS) {
    assertSourceIds(stack.sourceIds, sourceIds, `stack ${stack.id}`);
    for (const workloadPreset of data.WORKLOAD_PRESETS) {
      const stackResult = infra.calculateCostBreakdown(stack.assumptions, workloadPreset);
      assertFinitePositive(stackResult.costPer1MTokens, `${stack.id}/${workloadPreset.id} cost`);
      assertFinitePositive(
        stackResult.usefulTokensPerYear,
        `${stack.id}/${workloadPreset.id} tokens`,
      );
      const stackMonteCarlo = infra.runMonteCarlo(stack.assumptions, workloadPreset, 160, 11);
      if (!(stackMonteCarlo.p10.costPer1MTokens <= stackMonteCarlo.p50.costPer1MTokens)) {
        throw new Error(`${stack.id}/${workloadPreset.id}: P10 > P50`);
      }
      if (!(stackMonteCarlo.p50.costPer1MTokens <= stackMonteCarlo.p90.costPer1MTokens)) {
        throw new Error(`${stack.id}/${workloadPreset.id}: P50 > P90`);
      }
    }
  }

  for (const project of data.DATA_CENTER_PROJECTS) {
    assertSourceIds(project.sourceIds, sourceIds, `project ${project.id}`);
    const stack = data.STACK_PRESETS.find((item) => item.id === project.likelyStackId);
    if (!stack) throw new Error(`${project.id}: missing likely stack ${project.likelyStackId}`);

    for (const scenario of data.SCENARIO_PRESETS) {
      const probability = infra.scoreCompletionProbability(
        project,
        data.DEFAULT_PROBABILITY_WEIGHTS,
        scenario,
      );
      if (probability < 0 || probability > 1) {
        throw new Error(`${project.id}/${scenario.id}: invalid probability ${probability}`);
      }

      const forecast = infra.projectForecast(project, stack, data.WORKLOAD_PRESETS[0], scenario);
      if (forecast.length === 0) throw new Error(`${project.id}/${scenario.id}: empty forecast`);
      const onlineYears = forecast.filter((year) => year.mwOnline > 0);
      if (onlineYears.length === 0) {
        throw new Error(`${project.id}/${scenario.id}: no online capacity in forecast window`);
      }
      for (const year of onlineYears) {
        assertFinitePositive(year.equivalentStacks, `${project.id}/${scenario.id} stacks`);
        assertFinitePositive(year.annualUsefulTokens, `${project.id}/${scenario.id} tokens`);
        assertFinitePositive(year.costPer1MTokens, `${project.id}/${scenario.id} cost`);
      }
    }
  }

  const aggregate = infra.aggregateForecasts(
    data.DATA_CENTER_PROJECTS.map((project) => {
      const stack =
        data.STACK_PRESETS.find((item) => item.id === project.likelyStackId) ??
        data.STACK_PRESETS[0];
      return {
        project,
        years: infra.projectForecast(
          project,
          stack,
          data.WORKLOAD_PRESETS[0],
          data.SCENARIO_PRESETS[0],
        ),
      };
    }),
  );
  if (aggregate.length !== 4) throw new Error(`expected four company aggregates, got ${aggregate.length}`);
}

function assertSourceIds(ids, sourceIds, label) {
  for (const id of ids) {
    if (!sourceIds.has(id)) throw new Error(`${label}: missing source ${id}`);
  }
}

function assertFinitePositive(value, label) {
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error(`${label}: expected positive finite value, got ${value}`);
  }
}

// External-realism guardrail. Catches input typos that pass the internal-arithmetic
// checks but would publish nonsense numbers. The band is intentionally wide:
// frontier-API list prices currently sit near $3-15 per 1M output tokens; with a
// 70-80% gross margin on inference revenue, raw bottom-up cost should land roughly
// $0.10-$5 per 1M useful tokens. We allow up to $10 to leave room for the
// frontier-reasoning workload (long output, low throughput) and slow-stack outliers.
function validateSanityBands() {
  const productionAssistant = data.WORKLOAD_PRESETS.find((wl) => wl.id === "production-assistant");
  if (!productionAssistant) throw new Error("sanity check: production-assistant workload missing");
  const lowerBand = 0.1;
  const upperBand = 10.0;
  for (const stack of data.STACK_PRESETS) {
    const monteCarlo = infra.runMonteCarlo(stack.assumptions, productionAssistant, 400, 19);
    const p50 = monteCarlo.p50.costPer1MTokens;
    if (!Number.isFinite(p50) || p50 < lowerBand || p50 > upperBand) {
      throw new Error(
        `sanity: stack ${stack.id} on production-assistant P50 cost $${p50.toFixed(3)}/1M outside band [$${lowerBand}, $${upperBand}]`,
      );
    }
  }
}
