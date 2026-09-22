# Tests

Plain Node scripts. No framework, no dependencies, no build step — matching the
vanilla-JS frontend they test.

## Running

```bash
node tests/run.js          # all suites
node tests/to-csv.test.js  # one suite
```

Exits non-zero on any failure, so it can gate a deploy:

```bash
node tests/run.js && git push origin main
```

## How these test browser code

`app/static/js/app.js` is a browser script — it defines a global `App` object
and exports nothing, so it can't be `require`d. Rather than copy logic into the
tests (where it would drift from the real thing), `helpers.js` lifts a single
method out of the file's source text and evaluates it. The tests therefore
exercise the code that actually ships.

`extractAppMethod(name, params)` finds `    name(params)` in the App object
literal, brace-matches the body, and returns a callable function. It throws if
the method is missing or the braces are unbalanced — so renaming a tested method
fails loudly instead of silently passing.

## Suites

| File | Covers |
|---|---|
| `to-csv.test.js` | `App.toCsv()` quoting rules: commas, quotes, newlines, edge whitespace, null/undefined, numeric zero |
| `csv-export-roundtrip.test.js` | Payroll and income/expense exports: serialize realistic report rows, parse them back with an independent parser, confirm no field is split, shifted, or dropped |

The round-trip suite parses with its own RFC 4180 reader (`helpers.parseCsv`)
rather than reusing the writer, so a bug shared between the two cannot make a
test pass.

## Why these exist

Both CSV exports used to build rows with `row.join(',')` and hand-quote the
description field at each call site. That worked, but `Job.description` is
nullable and `null.replace()` throws — which would have killed an export with no
file produced and no error shown. Every other field was unquoted by
construction, so correctness depended on remembering the convention each time a
field was added.

`App.toCsv()` replaced that. These tests pin its behavior.

## Adding a suite

Create `tests/<name>.test.js`. Use `createChecker(suiteName)` for assertions and
exit with `summary() === 0 ? 0 : 1`. `run.js` picks up any `*.test.js`
automatically.

## Not covered

These test pure functions only. Anything needing a DOM, a live API, or the
database is out of scope — server-side behavior is verified by running scripts
against the app on the server (see `CLAUDE.md` → Running Server-Side Scripts).
