/**
 * Shared helpers for the test scripts.
 *
 * app.js is a browser script, not a module - it defines a global `App`
 * object and has no exports. Rather than duplicate its logic here, these
 * helpers lift a single method out of the file's source and evaluate it,
 * so the tests exercise the code that actually ships.
 */
const fs = require('fs');
const path = require('path');

const APP_JS = path.join(__dirname, '..', 'app', 'static', 'js', 'app.js');

/**
 * Extract a method from the App object literal in app.js and return it
 * as a callable function.
 *
 * @param {string} name   Method name, e.g. 'toCsv'
 * @param {string} params Parameter list as written, e.g. 'rows'
 */
function extractAppMethod(name, params) {
    const src = fs.readFileSync(APP_JS, 'utf8');
    const signature = `    ${name}(${params})`;
    const start = src.indexOf(signature);
    if (start === -1) {
        throw new Error(`App.${name}(${params}) not found in ${APP_JS}`);
    }

    // Walk braces from the start of the body to find its matching close
    const bodyStart = src.indexOf('{', start);
    let depth = 0;
    let i = bodyStart;
    for (; i < src.length; i++) {
        if (src[i] === '{') depth++;
        else if (src[i] === '}') {
            depth--;
            if (depth === 0) break;
        }
    }
    if (depth !== 0) {
        throw new Error(`Unbalanced braces while extracting App.${name}`);
    }

    const body = src.slice(bodyStart, i + 1);
    return eval(`(function ${name}(${params}) ${body})`);
}

/**
 * Returns a { check, summary } pair for assertions.
 * check() compares by structural equality and prints a PASS/FAIL line.
 */
function createChecker(suiteName) {
    let failures = 0;
    let total = 0;

    function check(label, actual, expected) {
        total++;
        const ok = JSON.stringify(actual) === JSON.stringify(expected);
        if (!ok) failures++;
        console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}`);
        if (!ok) {
            console.log(`        expected: ${JSON.stringify(expected)}`);
            console.log(`        actual:   ${JSON.stringify(actual)}`);
        }
    }

    function summary() {
        console.log(`\n${suiteName}: ${total - failures}/${total} passed`);
        return failures;
    }

    return { check, summary };
}

/**
 * Minimal RFC 4180 CSV parser, written independently of App.toCsv so a
 * round-trip test cannot pass by sharing the writer's bugs.
 */
function parseCsv(text) {
    const rows = [];
    let row = [];
    let field = '';
    let inQuotes = false;

    for (let i = 0; i < text.length; i++) {
        const c = text[i];
        if (inQuotes) {
            if (c === '"') {
                if (text[i + 1] === '"') {
                    field += '"';
                    i++;
                } else {
                    inQuotes = false;
                }
            } else {
                field += c;
            }
        } else if (c === '"') {
            inQuotes = true;
        } else if (c === ',') {
            row.push(field);
            field = '';
        } else if (c === '\n') {
            row.push(field);
            rows.push(row);
            row = [];
            field = '';
        } else {
            field += c;
        }
    }
    row.push(field);
    rows.push(row);
    return rows;
}

module.exports = { extractAppMethod, createChecker, parseCsv, APP_JS };
