/**
 * Unit tests for App.toCsv() - the CSV serializer shared by every
 * client-side export.
 */
const { extractAppMethod, createChecker } = require('./helpers');

const toCsv = extractAppMethod('toCsv', 'rows');
const { check, summary } = createChecker('App.toCsv');

console.log('=== App.toCsv ===');

check('plain values are not quoted',
    toCsv([['a', 'b', 'c']]), 'a,b,c');

check('comma forces quoting',
    toCsv([['Wichita, KS', 'x']]), '"Wichita, KS",x');

check('embedded quote is doubled and field quoted',
    toCsv([['say "hi"', 'x']]), '"say ""hi""",x');

check('newline forces quoting',
    toCsv([['line1\nline2', 'x']]), '"line1\nline2",x');

check('carriage return forces quoting',
    toCsv([['a\rb']]), '"a\rb"');

check('leading/trailing space forces quoting',
    toCsv([[' padded ']]), '" padded "');

// Job.description is a nullable column - the old hand-rolled quoting
// called .replace() on it and threw, killing the whole export.
check('null becomes an empty field (no crash)',
    toCsv([[null, 'x']]), ',x');

check('undefined becomes an empty field (no crash)',
    toCsv([[undefined, 'x']]), ',x');

check('zero is preserved, not treated as empty',
    toCsv([[0, 'x']]), '0,x');

check('numbers are stringified',
    toCsv([[1.5, 2]]), '1.5,2');

check('empty row yields an empty line',
    toCsv([['a'], [], ['b']]), 'a\n\nb');

check('multiple rows joined with newline',
    toCsv([['a', 'b'], ['c', 'd']]), 'a,b\nc,d');

check('real job description containing commas',
    toCsv([['2026-08-31', 'WM-3137622819',
        '05948765 - 293 S. Greenwich Rd, Wichita KS, epik box swap', '2.62']]),
    '2026-08-31,WM-3137622819,"05948765 - 293 S. Greenwich Rd, Wichita KS, epik box swap",2.62');

process.exit(summary() === 0 ? 0 : 1);
