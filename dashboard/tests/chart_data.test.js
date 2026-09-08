/** Verify calendar totals, missing observations and exact exported chart values. */
import assert from "node:assert/strict";
import test from "node:test";
import { aggregatePerformance, safeRatio, rowsToCsv } from "../src/lib/chartData.js";
import { money, compactMoney, count, percent, ratio } from "../src/theme.js";

test("all metric formatters keep absent input unavailable and measured zero visible", () => {
  for (const format of [money, compactMoney, count, percent, ratio]) {
    for (const value of [null, undefined, "", NaN, Infinity]) assert.equal(format(value), "--");
    assert.notEqual(format(0), "--");
  }
});

test("weekly and monthly grouping recomputes ratios from additive observations", () => {
  const rows = [
    { report_date: "2026-01-31", cost: 10, sales: 100, clicks: 1 },
    { report_date: "2026-02-01", cost: 90, sales: 90, clicks: 9 },
    { report_date: "2026-02-02", cost: 0, sales: 5, clicks: 0 },
  ];
  const weeks = aggregatePerformance(rows, "week");
  assert.deepEqual(weeks.map(x => x.key), ["2026-01-26", "2026-02-02"]);
  assert.equal(weeks[0].roas, 1.9);
  assert.equal(weeks[0].clicks, 10);
  assert.equal(weeks[1].roas, null);
  assert.deepEqual(aggregatePerformance(rows, "month").map(x => x.sales), [100, 95]);
});

test("missing is distinct from zero and input rows remain immutable", () => {
  assert.equal(safeRatio(0, 3), 0);
  for (const pair of [[1, 0], [null, 2], [2, null], [Infinity, 3]]) assert.equal(safeRatio(...pair), null);
  const rows = Object.freeze([Object.freeze({ report_date: "2026-01-01", cost: 0, sales: null })]);
  const [result] = aggregatePerformance(rows);
  assert.equal(result.cost, 0);
  assert.equal(result.sales, null);
  assert.equal(result.roas, null);
  assert.deepEqual(aggregatePerformance([]), []);
});

test("100,000 observations use bounded calendar output", () => {
  const rows = Array.from({ length: 100000 }, (_, i) => ({ report_date: `2026-01-${String(i % 28 + 1).padStart(2, "0")}`, cost: 2, sales: 6 }));
  const totals = aggregatePerformance(rows, "month");
  assert.equal(totals.length, 1);
  assert.equal(totals[0].cost, 200000);
  assert.equal(totals[0].roas, 3);
  assert.equal(totals[0].rows, 100000);
});

test("export preserves filtered raw values, escapes cells and blanks unavailable values", () => {
  const csv = rowsToCsv([{ key: "name", label: "Name" }, { key: "value", label: "Value" }], [
    { name: 'A,"B"', value: 0 }, { name: "=SUM(A1)", value: null },
  ]);
  assert.equal(csv, 'Name,Value\r\n"A,""B""",0\r\n\'=SUM(A1),\r\n');
});
