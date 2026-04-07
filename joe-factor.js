/**
 * JOE Factor — Fantasy Baseball Luck Calculator
 *
 * Calculates how lucky or unlucky each team was based on scheduling.
 * For every week, each team's stats are compared category-by-category
 * against every other team. This produces:
 *   - Best Case:    win% if they'd faced the weakest possible opponent
 *   - Worst Case:   win% if they'd faced the strongest possible opponent
 *   - Average Case: win% averaged across all possible opponents
 *   - Actual:       win% against their real scheduled opponent
 *   - Luck:         Actual − Average Case
 *
 * SCORING RULES (10 categories, matches the original spreadsheet):
 *   Higher is better: R, HR, RBI, SB, AVG, K, W, SV
 *   Lower is better:  ERA, WHIP
 *   Win  = 1 pt  |  Tie = 0.5 pts  |  Loss = 0 pts
 *   Win% = (wins + 0.5 * ties) / 10
 */

// ---------------------------------------------------------------------------
// Types (JSDoc — works in plain JS and TypeScript)
// ---------------------------------------------------------------------------

/**
 * @typedef {Object} TeamWeekStats
 * @property {string} team   - Team name
 * @property {number} week   - Week number (1-based)
 * @property {number} R      - Runs
 * @property {number} HR     - Home runs
 * @property {number} RBI    - Runs batted in
 * @property {number} SB     - Stolen bases
 * @property {number} AVG    - Batting average
 * @property {number} K      - Strikeouts (pitching)
 * @property {number} W      - Wins (pitching)
 * @property {number} SV     - Saves
 * @property {number} ERA    - Earned run average (lower is better)
 * @property {number} WHIP   - Walks + hits per inning pitched (lower is better)
 */

/**
 * @typedef {Object} WeekResult
 * @property {string} team
 * @property {number} week
 * @property {string} opponent        - Actual scheduled opponent
 * @property {number} actual          - Win% vs actual opponent
 * @property {number} bestCase        - Highest possible win% that week
 * @property {string} bestOpponent    - Who they would have beaten most
 * @property {number} worstCase       - Lowest possible win% that week
 * @property {string} worstOpponent   - Who would have beaten them most
 * @property {number} avgCase         - Mean win% vs all opponents
 * @property {number} luck            - actual − avgCase
 * @property {Object} vsAll          - win% vs every team { teamName: winPct }
 */

/**
 * @typedef {Object} SeasonSummary
 * @property {string} team
 * @property {number} avgActual
 * @property {number} avgBestCase
 * @property {number} avgWorstCase
 * @property {number} avgCase
 * @property {number} luck            - avgActual − avgCase (season-level)
 * @property {WeekResult[]} weeks
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CATEGORIES_HIGH = ['R', 'HR', 'RBI', 'SB', 'AVG', 'K', 'W', 'SV']; // higher = better
const CATEGORIES_LOW  = ['ERA', 'WHIP'];                                     // lower  = better
const ALL_CATEGORIES  = [...CATEGORIES_HIGH, ...CATEGORIES_LOW];
const NUM_CATEGORIES  = ALL_CATEGORIES.length; // 10

// ---------------------------------------------------------------------------
// Core helpers
// ---------------------------------------------------------------------------

/**
 * Compare two team-week stat lines category by category.
 * Returns win% for teamA (0–1).
 *
 * @param {TeamWeekStats} a
 * @param {TeamWeekStats} b
 * @returns {number} win% for team A
 */
function headToHead(a, b) {
  let points = 0;

  for (const cat of CATEGORIES_HIGH) {
    if (a[cat] > b[cat])      points += 1;
    else if (a[cat] === b[cat]) points += 0.5;
    // loss = 0
  }

  for (const cat of CATEGORIES_LOW) {
    if (a[cat] < b[cat])      points += 1;   // lower ERA/WHIP wins
    else if (a[cat] === b[cat]) points += 0.5;
  }

  return points / NUM_CATEGORIES;
}

/**
 * Round to a given number of decimal places (avoids floating-point drift).
 * @param {number} n
 * @param {number} [decimals=6]
 * @returns {number}
 */
function round(n, decimals = 6) {
  return Math.round(n * 10 ** decimals) / 10 ** decimals;
}

// ---------------------------------------------------------------------------
// Main calculation
// ---------------------------------------------------------------------------

/**
 * Calculate the JOE Factor for every team and week.
 *
 * @param {TeamWeekStats[]} stats        - All team-week stat lines
 * @param {Array<{week: number, away: string, home: string}>} schedule
 *   - The actual matchups. Each entry is one game. Both `away` and `home`
 *     must match team names in `stats` exactly.
 * @returns {{ byTeamWeek: WeekResult[], season: SeasonSummary[] }}
 */
function calculateJOEFactor(stats, schedule) {
  // Group stats by week
  const byWeek = {};
  for (const row of stats) {
    if (!byWeek[row.week]) byWeek[row.week] = [];
    byWeek[row.week].push(row);
  }

  // Build a lookup: week → { teamName → opponent }
  const actualOpponent = {};
  for (const game of schedule) {
    if (!actualOpponent[game.week]) actualOpponent[game.week] = {};
    actualOpponent[game.week][game.away] = game.home;
    actualOpponent[game.week][game.home] = game.away;
  }

  const weekResults = [];

  for (const [weekStr, weekTeams] of Object.entries(byWeek)) {
    const week = Number(weekStr);

    for (const teamRow of weekTeams) {
      const opponents = weekTeams.filter(t => t.team !== teamRow.team);
      if (opponents.length === 0) continue;

      const vsAll = {};
      for (const opp of opponents) {
        vsAll[opp.team] = round(headToHead(teamRow, opp));
      }

      const winPcts = Object.values(vsAll);
      const avgCase  = round(winPcts.reduce((s, v) => s + v, 0) / winPcts.length);
      const bestCase = round(Math.max(...winPcts));
      const worstCase = round(Math.min(...winPcts));

      const bestOpponent  = opponents.find(o => round(headToHead(teamRow, o)) === bestCase)?.team  ?? '';
      const worstOpponent = opponents.find(o => round(headToHead(teamRow, o)) === worstCase)?.team ?? '';

      const scheduledOpponent = actualOpponent[week]?.[teamRow.team] ?? null;
      const actual = scheduledOpponent != null
        ? round(vsAll[scheduledOpponent] ?? 0)
        : null; // week not scheduled yet

      const luck = actual != null ? round(actual - avgCase) : null;

      weekResults.push({
        team: teamRow.team,
        week,
        opponent: scheduledOpponent,
        actual,
        bestCase,
        bestOpponent,
        worstCase,
        worstOpponent,
        avgCase,
        luck,
        vsAll,
      });
    }
  }

  // Sort for readability
  weekResults.sort((a, b) => a.week - b.week || a.team.localeCompare(b.team));

  // Aggregate season-level summaries (only over weeks where actual is known)
  const teamNames = [...new Set(stats.map(s => s.team))];

  // Step 1 — per-team stats
  const teamSummaries = teamNames.map(team => {
    const weeks = weekResults.filter(r => r.team === team && r.actual != null);
    const avg = arr => arr.length ? arr.reduce((s, v) => s + v, 0) / arr.length : null;

    const avgActual     = round(avg(weeks.map(w => w.actual)));
    const avgBestCase   = round(avg(weeks.map(w => w.bestCase)));
    const avgWorstCase  = round(avg(weeks.map(w => w.worstCase)));
    const avgCaseSeason = round(avg(weeks.map(w => w.avgCase)));

    // Weekly differences: actual - avgCase per week
    const diffs = weeks.map(w => w.actual - w.avgCase);
    const meanDiff = diffs.length ? diffs.reduce((s, v) => s + v, 0) / diffs.length : null;

    // Std deviation of weekly differences (team's own variance)
    let stdDiff = null;
    if (diffs.length >= 2) {
      const variance = diffs.reduce((s, v) => s + (v - meanDiff) ** 2, 0) / (diffs.length - 1);
      stdDiff = Math.sqrt(variance);
    }

    // JOE Factor = mean(diff) / std(diff)  — t-statistic style
    const joeFactor = (meanDiff != null && stdDiff != null && stdDiff > 0)
      ? round(meanDiff / stdDiff)
      : (meanDiff != null ? round(meanDiff * 10) : null); // fallback for 1-week seasons

    return {
      team,
      avgActual,
      avgBestCase,
      avgWorstCase,
      avgCase: avgCaseSeason,
      luck: joeFactor,          // raw JOE Factor (t-statistic)
      joeRaw: joeFactor,
      weeks: weeks.sort((a, b) => a.week - b.week),
    };
  });

  // Step 2 — min-max normalize luck to [-1, +1] across all teams
  const rawValues = teamSummaries.map(t => t.joeRaw).filter(v => v != null);
  const minRaw = rawValues.length ? Math.min(...rawValues) : -1;
  const maxRaw = rawValues.length ? Math.max(...rawValues) :  1;
  const rangeRaw = maxRaw - minRaw;

  const season = teamSummaries.map(t => {
    const normalized = (t.joeRaw != null && rangeRaw > 0)
      ? round(2 * (t.joeRaw - minRaw) / rangeRaw - 1)
      : 0;
    return {
      ...t,
      luck: normalized,         // normalized [-1, +1] for display
      joeRaw: t.joeRaw,         // raw t-statistic for reference
    };
  }).sort((a, b) => (b.avgActual ?? -1) - (a.avgActual ?? -1));

  return { byTeamWeek: weekResults, season };
}

// ---------------------------------------------------------------------------
// Exports — works in Node (CommonJS), ES modules, and browser globals
// ---------------------------------------------------------------------------

const JOEFactor = {
  calculateJOEFactor,
  headToHead,
  CATEGORIES_HIGH,
  CATEGORIES_LOW,
  ALL_CATEGORIES,
  NUM_CATEGORIES,
};

// Node / bundler
if (typeof module !== 'undefined' && module.exports) {
  module.exports = JOEFactor;
}
// ES module
if (typeof exports !== 'undefined') {
  Object.assign(exports, JOEFactor);
}
// Browser global
if (typeof window !== 'undefined') {
  window.JOEFactor = JOEFactor;
}
