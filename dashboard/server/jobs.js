/**
 * Run a pipeline stage from the dashboard and stream its progress back.
 *
 * The three model stages -- attribution, strategy optimization, and strategy
 * evaluation -- already exist as command-line scripts. This module runs one of
 * those, exactly as the documented command would, and keeps its output where
 * the client can poll it. It does not reimplement any stage: a run started here
 * and a run started in a terminal execute the same script with the same
 * arguments, so the dashboard cannot drift from the pipeline it reports on.
 *
 * Why a poll rather than a socket: the client already polls `/api/settings` for
 * the rail's status, the runs are minutes rather than milliseconds, and a
 * dropped connection during a five-minute fit should not abandon the run. The
 * job outlives the request that started it.
 *
 * Running a stage writes files under `modules/`, so it is refused wherever the
 * deployment is read-only -- the published static build has no server at all,
 * and a protected server deployment has a configuration it must not rewrite.
 * It is additionally gated on a configured database, because a stage's whole
 * purpose here is to refresh what the dashboard reads.
 *
 * Data flow:
 *     POST /api/jobs -> here -> uv run script/*.py -> modules/&#42;/outputs
 *     GET  /api/jobs -> here -> the Campaign Optimizer's log tabs
 */

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

import { REPO_ROOT, simulatorDataDirectory } from "./config.js";

/**
 * How many output lines one run keeps.
 *
 * A fit over a research-scale snapshot can print thousands; the reader wants
 * the shape of the run and its tail, and an unbounded buffer in a long-lived
 * server process is a leak. The count of dropped lines is reported rather than
 * hidden, so a truncated log never reads as a complete one.
 */
const MAX_LINES = 600;

/** Completed runs kept for inspection after they finish. */
const MAX_HISTORY = 6;

/**
 * The three stages, in pipeline order.
 *
 * Each names the script it runs and the phases it passes through. The phases
 * are matched against the script's own stdout to advance the progress bar:
 * a stage reports where it actually is rather than against a timer, so a slow
 * fit shows as a slow phase instead of a bar that reaches 90% and stops.
 */
export const STAGES = {
  attribution: {
    label: "MTA attribution",
    script: "script/run_pipeline.py",
    /**
     * `run_pipeline.py` rather than `run_attribution_models.py`: the pipeline
     * script rebuilds the path report from the touchpoint events first and
     * publishes all five outputs atomically, which is what the documented
     * command does and what keeps a failed run from leaving half a result.
     *
     * Each pattern matches a line `run_pipeline.py` and
     * `run_attribution_models.py` print from their `progress` hooks, so the
     * phases and the script's own stage boundaries cannot drift apart.
     */
    phases: [
      { at: 8, match: /aggregated path report/i, message: "Building the aggregated path report" },
      { at: 30, match: /Markov removal-effect/i, message: "Running Markov removal-effect attribution" },
      { at: 55, match: /Shapley/i, message: "Running path-level Shapley attribution" },
      { at: 80, match: /Comparing models/i, message: "Comparing models and judging reliability" },
      { at: 92, match: /Publishing the attribution outputs/i, message: "Publishing the attribution outputs" },
    ],
  },
  optimization: {
    label: "MTA strategy optimization",
    script: "script/generate_campaign_strategy.py",
    /**
     * Needs a research snapshot to fit budget response against, which is the
     * one input the committed reports do not supply: fitting a
     * budget-to-revenue curve needs the same Campaign observed at several
     * budget levels, and a single reporting window carries one.
     */
    requiresResearchSnapshot: true,
    phases: [
      { at: 10, match: /load|snapshot/i, message: "Loading Campaign budget observations" },
      { at: 35, match: /dataset|observation/i, message: "Building the response dataset" },
      { at: 60, match: /fit|model/i, message: "Fitting budget-to-spend and spend-to-revenue curves" },
      { at: 85, match: /optimi|allocat|solver/i, message: "Equalizing marginal return across Campaigns" },
      { at: 95, match: /wrote|written/i, message: "Writing the optimized strategy" },
    ],
  },
  evaluation: {
    label: "MTA strategy evaluation",
    /**
     * `modules/mta_strategy_evaluation/` is specified but not built, so there
     * is no script to run. The stage is declared here with the reason rather
     * than omitted, so the view can show three tabs and say plainly why the
     * third cannot run yet — a missing tab reads as a dashboard defect, while
     * a named unbuilt stage reads as the roadmap it is.
     */
    script: null,
    unavailableReason:
      "The strategy evaluation layer is specified but not yet built: " +
      "modules/mta_strategy_evaluation/ and script/evaluate_strategies.py do " +
      "not exist. Attribution model evaluation against ground truth is " +
      "available in modules/mta_standard/src/evaluation.py.",
    phases: [],
  },
};

export const STAGE_KEYS = Object.keys(STAGES);

/** The most recent run of each stage, keyed by stage. */
const running = new Map();
const history = [];

let nextId = 1;

function nowIso() {
  return new Date().toISOString();
}

/**
 * A run's public shape.
 *
 * The command is included so a reader can reproduce the run in a terminal,
 * which is the point of running the real script rather than a reimplementation.
 */
function publicView(job) {
  return {
    id: job.id,
    stage: job.stage,
    label: STAGES[job.stage]?.label ?? job.stage,
    state: job.state,
    percent: job.percent,
    phase: job.phase,
    command: job.command,
    startedAt: job.startedAt,
    finishedAt: job.finishedAt,
    exitCode: job.exitCode,
    error: job.error,
    lines: job.lines,
    droppedLines: job.droppedLines,
  };
}

function append(job, stream, text) {
  for (const raw of String(text).split(/\r?\n/)) {
    const line = raw.replace(/\s+$/, "");
    if (line === "") continue;
    job.lines.push({ at: nowIso(), stream, text: line.slice(0, 500) });
    if (job.lines.length > MAX_LINES) {
      job.droppedLines += job.lines.length - MAX_LINES;
      job.lines.splice(0, job.lines.length - MAX_LINES);
    }
    advance(job, line);
  }
}

/**
 * Move the progress bar to the furthest phase the output has reached.
 *
 * Monotonic by construction: a later line matching an earlier phase never
 * walks the bar backwards, which a naive last-match-wins rule would do as soon
 * as one stage's summary mentions a previous stage by name.
 */
function advance(job, line) {
  for (const phase of STAGES[job.stage]?.phases ?? []) {
    if (phase.match.test(line) && phase.at > job.percent) {
      job.percent = phase.at;
      job.phase = phase.message;
    }
  }
}

/** The run of `stage` that is still going, if any. */
export function activeJob(stage) {
  const job = running.get(stage);
  return job && job.state === "running" ? job : null;
}

/**
 * Every stage's current or most recent run, plus what each stage can do.
 *
 * Returned whole rather than per stage, because the view shows three tabs at
 * once and polling three endpoints to fill them would be three times the
 * requests for one screen.
 */
export function jobsState() {
  const stages = {};
  for (const key of STAGE_KEYS) {
    const definition = STAGES[key];
    const job = running.get(key) ?? null;
    stages[key] = {
      key,
      label: definition.label,
      script: definition.script,
      available: Boolean(definition.script),
      unavailableReason: definition.unavailableReason ?? null,
      requiresResearchSnapshot: Boolean(definition.requiresResearchSnapshot),
      current: job ? publicView(job) : null,
    };
  }
  return { stages, history: history.map(publicView) };
}

/**
 * Why `stage` cannot be started right now, or null when it can.
 *
 * Every reason is checked before anything is spawned, so a refusal never
 * leaves a half-started run behind, and each names the remedy rather than only
 * the fault.
 */
export function startRefusal(stage, { writable }) {
  const definition = STAGES[stage];
  if (!definition) return { code: "unknown_stage", message: `Unknown stage: ${stage}.` };
  if (!definition.script) {
    return { code: "stage_unavailable", message: definition.unavailableReason };
  }
  if (!writable) {
    return {
      code: "read_only",
      message:
        "Running a stage writes new outputs, so it needs a connected " +
        "database deployment. This deployment reads committed files.",
    };
  }
  if (activeJob(stage)) {
    return {
      code: "already_running",
      message: `${definition.label} is already running.`,
    };
  }
  if (definition.requiresResearchSnapshot && !researchSnapshotPath()) {
    return {
      code: "missing_input",
      message:
        "Fitting a budget response curve needs the same Campaign observed at " +
        "several budget levels, which a single reporting window does not " +
        "carry. Configure MTA_SIM_DATA_DIR with a research snapshot to fit " +
        "against.",
    };
  }
  return null;
}

/** The research snapshot the optimizer fits against, when one is configured. */
function researchSnapshotPath() {
  const directory = simulatorDataDirectory();
  if (!directory) return null;
  const path = resolve(directory, "simulation_research.json");
  return existsSync(path) ? path : null;
}

/**
 * Build the argument list for a stage.
 *
 * A date range narrows the reporting window the stage reads. It is validated
 * to `YYYY-MM-DD` before it reaches the command line rather than passed
 * through, so a value from the browser cannot become part of a command.
 */
function argumentsFor(stage, options) {
  const args = ["run", "python", "-X", "utf8", "-B", STAGES[stage].script];
  if (stage === "attribution") {
    // The window narrows both the Ads report and the touchpoint events, so the
    // two stay coherent: the pipeline rejects a conversion whose event time
    // falls outside the window its Ads report infers.
    if (options.startDate) args.push("--report-start-date", options.startDate);
    if (options.endDate) args.push("--report-end-date", options.endDate);
  }
  if (stage === "optimization") {
    args.push("--research-snapshot", researchSnapshotPath());
    if (Number.isFinite(options.totalBudget) && options.totalBudget > 0) {
      args.push("--total-budget", String(options.totalBudget));
    }
    if (options.budgetUsagePolicy) {
      args.push("--budget-usage-policy", options.budgetUsagePolicy);
    }
  }
  return args;
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Validate what the client asked for.
 *
 * Returns a normalized options object or throws with the specific complaint.
 * Rejecting here rather than at the command line is what keeps an unchecked
 * string out of `spawn`'s argument vector.
 */
export function normalizeOptions(body = {}) {
  const options = {};
  for (const key of ["startDate", "endDate"]) {
    const value = String(body[key] ?? "").trim();
    if (value === "") continue;
    if (!ISO_DATE.test(value)) {
      throw new Error(`${key} must be a YYYY-MM-DD date.`);
    }
    options[key] = value;
  }
  if (options.startDate && options.endDate && options.startDate > options.endDate) {
    throw new Error("startDate must not be after endDate.");
  }
  if (body.totalBudget !== undefined && body.totalBudget !== null && body.totalBudget !== "") {
    const budget = Number(body.totalBudget);
    if (!Number.isFinite(budget) || budget <= 0) {
      throw new Error("totalBudget must be a positive number.");
    }
    options.totalBudget = budget;
  }
  const policy = String(body.budgetUsagePolicy ?? "").trim();
  if (policy !== "") {
    // Exactly the values `BudgetUsagePolicy` declares in
    // modules/mta_common/src/enums.py. Anything else would reach argparse's
    // `choices` and fail the run after it had already started.
    if (!["SPEND_FULL_BUDGET", "SPEND_UP_TO_BUDGET"].includes(policy)) {
      throw new Error("budgetUsagePolicy is not a recognized policy.");
    }
    options.budgetUsagePolicy = policy;
  }
  return options;
}

/**
 * Start `stage` and return its run immediately.
 *
 * The caller has already checked `startRefusal`. The child is detached from the
 * request: the HTTP response returns as soon as the process is spawned, and the
 * client polls for the rest.
 */
export function startJob(stage, options, { onFinish } = {}) {
  const args = argumentsFor(stage, options);
  const job = {
    id: nextId++,
    stage,
    state: "running",
    percent: 2,
    phase: "Starting",
    command: `uv ${args.join(" ")}`,
    startedAt: nowIso(),
    finishedAt: null,
    exitCode: null,
    error: null,
    lines: [],
    droppedLines: 0,
    child: null,
  };
  running.set(stage, job);

  append(job, "meta", `$ ${job.command}`);
  if (options.startDate || options.endDate) {
    append(
      job,
      "meta",
      `Reporting window: ${options.startDate ?? "earliest"} to ${options.endDate ?? "latest"}`,
    );
  }

  let child;
  try {
    child = spawn("uv", args, {
      cwd: REPO_ROOT,
      // `shell: false` is the default and is what keeps the arguments an
      // argument vector rather than a string a shell would re-parse.
      env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUNBUFFERED: "1" },
      windowsHide: true,
    });
  } catch (error) {
    finish(job, { error: `${error.name}: ${error.message}` }, onFinish);
    return job;
  }

  job.child = child;
  child.stdout?.on("data", (chunk) => append(job, "stdout", chunk));
  child.stderr?.on("data", (chunk) => append(job, "stderr", chunk));

  child.on("error", (error) => {
    const missing = error.code === "ENOENT";
    finish(
      job,
      {
        error: missing
          ? "The `uv` command was not found on this server. The dashboard runs " +
            "pipeline stages through uv, exactly as the documented commands do; " +
            "install uv, or run the stage in a terminal instead."
          : `${error.name}: ${error.message}`,
      },
      onFinish,
    );
  });

  child.on("close", (code) => {
    if (job.state !== "running") return;
    finish(job, { exitCode: code }, onFinish);
  });

  return job;
}

function finish(job, { exitCode = null, error = null }, onFinish) {
  job.state = error || exitCode !== 0 ? "failed" : "succeeded";
  job.exitCode = exitCode;
  job.error = error;
  job.finishedAt = nowIso();
  job.child = null;
  if (job.state === "succeeded") {
    job.percent = 100;
    job.phase = "Complete";
    append(job, "meta", "Stage completed. Reloading the dashboard's data.");
  } else {
    append(job, "meta", error ?? `Stage failed with exit code ${exitCode}.`);
    job.phase = "Failed";
  }

  history.unshift(job);
  if (history.length > MAX_HISTORY) history.length = MAX_HISTORY;

  // Only a successful run changed what the dashboard reads.
  if (job.state === "succeeded") onFinish?.(job);
}

/** Stop a running stage. Used by the view's Stop control. */
export function stopJob(stage) {
  const job = activeJob(stage);
  if (!job?.child) return false;
  append(job, "meta", "Stop requested by the operator.");
  job.child.kill();
  return true;
}
