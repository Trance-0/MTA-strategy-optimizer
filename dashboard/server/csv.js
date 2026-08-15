/**
 * Minimal RFC 4180 CSV reader for the project's committed artifacts.
 *
 * The dashboard reads a fixed set of files the pipeline writes, so this parser
 * covers exactly what those files contain -- quoted fields, doubled quotes
 * inside them, and both line endings -- rather than pulling in a dependency.
 * It deliberately does no type inference: every value comes back as a string
 * and `data_source.js` coerces the columns it knows about, because inference
 * is what makes a file read and a database read disagree.
 *
 * Data flow:
 *     modules/&#42;/data and outputs -> here -> server/data_source.js
 */

import { readFileSync } from "node:fs";

import { DESCRIPTION_ROW_MARKERS } from "./config.js";

/**
 * Split CSV text into rows of raw string cells.
 *
 * A quoted field may contain commas, newlines, and doubled quotes; everything
 * else is taken literally.
 */
export function parseCsv(text) {
  // A UTF-8 byte-order mark would otherwise become part of the first header
  // name, so every lookup of that column would miss.
  const source = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;

  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;

  for (let index = 0; index < source.length; index += 1) {
    const character = source[index];

    if (quoted) {
      if (character !== '"') {
        field += character;
      } else if (source[index + 1] === '"') {
        field += '"';
        index += 1;
      } else {
        quoted = false;
      }
      continue;
    }

    if (character === '"') {
      quoted = true;
    } else if (character === ",") {
      row.push(field);
      field = "";
    } else if (character === "\n" || character === "\r") {
      // Treat CRLF as one terminator rather than two empty rows.
      if (character === "\r" && source[index + 1] === "\n") index += 1;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += character;
    }
  }

  if (field !== "" || row.length > 0) {
    row.push(field);
    rows.push(row);
  }

  return rows;
}

/**
 * Read a project CSV as objects keyed by header name, dropping the Chinese
 * field-description row.
 *
 * Only the Amazon Ads and path-report samples carry that row, directly under
 * the header. It must go before any numeric column is parsed, or every numeric
 * conversion in that column fails. The check matches the exact marker rather
 * than guessing, because a heuristic would silently discard a real data row
 * from the files that have no description row.
 */
export function readCsv(path) {
  const rows = parseCsv(readFileSync(path, "utf8"));
  if (rows.length === 0) return [];

  const header = rows[0].map((name) => name.trim());
  let body = rows.slice(1);
  if (body.length > 0 && DESCRIPTION_ROW_MARKERS.includes(body[0][0])) {
    body = body.slice(1);
  }

  return body
    // A trailing newline yields a final row of one empty cell, which is not a
    // record and would otherwise become a row of nulls in every chart.
    .filter((cells) => cells.length > 1 || (cells[0] ?? "") !== "")
    .map((cells) => {
      const record = {};
      header.forEach((name, index) => {
        record[name] = cells[index] ?? "";
      });
      return record;
    });
}
