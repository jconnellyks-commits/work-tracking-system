#!/usr/bin/env node
/**
 * Runs every *.test.js in this directory.
 * Exits non-zero if any suite fails, so it works in a pre-deploy check.
 */
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const files = fs.readdirSync(__dirname)
    .filter(f => f.endsWith('.test.js'))
    .sort();

if (files.length === 0) {
    console.error('No test files found in ' + __dirname);
    process.exit(1);
}

let failed = [];

for (const file of files) {
    console.log(`\n${'-'.repeat(60)}\n${file}\n${'-'.repeat(60)}`);
    const result = spawnSync(process.execPath, [path.join(__dirname, file)], {
        stdio: 'inherit'
    });
    if (result.status !== 0) failed.push(file);
}

console.log(`\n${'='.repeat(60)}`);
if (failed.length === 0) {
    console.log(`ALL SUITES PASSED (${files.length})`);
    process.exit(0);
}
console.log(`FAILED: ${failed.join(', ')}`);
process.exit(1);
