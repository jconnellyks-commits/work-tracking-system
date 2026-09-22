/**
 * Round-trip tests for the payroll and income/expense CSV exports.
 *
 * Builds row arrays shaped exactly as Pages.exportPayrollCSV and
 * Pages.exportIncomeCSV build them, serializes with the shipped
 * App.toCsv, parses the result with an independent parser, and confirms
 * no field is split, shifted, or dropped.
 */
const { extractAppMethod, createChecker, parseCsv } = require('./helpers');

const toCsv = extractAppMethod('toCsv', 'rows');
const { check, summary } = createChecker('CSV export round-trip');

console.log('=== payroll export round-trip ===');

const payrollRows = [
    ['Payroll Report'],
    ['Period: 2026-08-01 to 2026-08-31'],
    [],
    ['Date', 'Ticket', 'Description', 'Hours', 'Rate', 'Using Min', 'Base Pay'],
    ['2026-08-31', 'WM-3137622819',
        '05948765 - 293 S. Greenwich Rd, Wichita KS, epik box swap',
        '2.62', '45.00', 'No', '117.90'],
    ['2026-08-30', 'FN-19904034',
        'Hanwha Techwin QNP6250 || Tech to "return to factory default"',
        '3.65', '45.00', 'No', '164.25'],
    // Used to throw: .replace() on a null description
    ['2026-08-29', 'TL-398586', null, '1.00', '45.00', 'No', '45.00'],
    ['TOTALS', '', '', '7.27', '', '', '327.15'],
];

const payroll = parseCsv(toCsv(payrollRows));

check('row count preserved', payroll.length, payrollRows.length);

check('comma description lands in one field',
    payroll[4][2], '05948765 - 293 S. Greenwich Rd, Wichita KS, epik box swap');

check('columns after a comma field are not shifted',
    payroll[4].slice(3), ['2.62', '45.00', 'No', '117.90']);

check('description with embedded quotes survives',
    payroll[5][2], 'Hanwha Techwin QNP6250 || Tech to "return to factory default"');

check('null description becomes empty, row intact',
    payroll[6], ['2026-08-29', 'TL-398586', '', '1.00', '45.00', 'No', '45.00']);

check('every data row has the header field count',
    payroll.slice(3).map(r => r.length), [7, 7, 7, 7, 7]);

check('totals row intact',
    payroll[7], ['TOTALS', '', '', '7.27', '', '', '327.15']);

console.log('\n=== income/expense export round-trip ===');

const incomeRows = [
    ['Income/Expense Report'],
    ['DETAILS'],
    ['Date', 'Ticket', 'Description', 'Platform', 'Income', 'Net Profit'],
    ['2026-08-31', 'WM-3128952561',
        'Chase New Build - Maize and Central Park, Install Door Hours',
        'WorkMarket', '450.00', '285.50'],
    ['2026-08-30', 'TST-502861', null, 'Tech Service Today', '300.00', '180.00'],
];

const income = parseCsv(toCsv(incomeRows));

check('comma description contained',
    income[3][2], 'Chase New Build - Maize and Central Park, Install Door Hours');

check('platform column not shifted by a preceding comma',
    income[3][3], 'WorkMarket');

check('money columns not shifted',
    income[3].slice(4), ['450.00', '285.50']);

check('null description row intact',
    income[4], ['2026-08-30', 'TST-502861', '', 'Tech Service Today', '300.00', '180.00']);

console.log('\n=== fields that were previously unquoted ===');

// The payroll export writes `TECHNICIAN: ${tech.tech_name}` as a bare row
const techRows = [['TECHNICIAN: Baugher, Geoffery Jr.'], ['Min Pay: $45.00/hr']];
check('tech name with a comma stays in one field',
    parseCsv(toCsv(techRows))[0], ['TECHNICIAN: Baugher, Geoffery Jr.']);

process.exit(summary() === 0 ? 0 : 1);
