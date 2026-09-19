#!/usr/bin/env node
"use strict";
/*
 * Copy `src/pagelore/` into `npm/vendor/pagelore/` so the tarball carries the
 * program rather than a dependency on it.
 *
 * Run by `prepack` and `prepare`, so `npm pack`, `npm publish` and a git install
 * all produce the same tree, and `vendor/` is gitignored — one copy in version
 * control, and it is the one under `src/`. CI hash-compares the two after a pack,
 * because a stale vendored copy is a version of this program nobody can find the
 * source of.
 */
const fs = require("fs");
const path = require("path");

const HERE = __dirname;
const SOURCE = path.join(HERE, "..", "..", "src", "pagelore");
const TARGET = path.join(HERE, "..", "vendor", "pagelore");
const SKIP = new Set(["__pycache__", ".DS_Store"]);

function copy(from, to) {
  fs.mkdirSync(to, { recursive: true });
  for (const entry of fs.readdirSync(from, { withFileTypes: true })) {
    if (SKIP.has(entry.name) || entry.name.endsWith(".pyc")) continue;
    const src = path.join(from, entry.name);
    const dst = path.join(to, entry.name);
    if (entry.isDirectory()) copy(src, dst);
    else fs.copyFileSync(src, dst);
  }
}

if (!fs.existsSync(SOURCE)) {
  // A published tarball has no `src/` beside it — it already carries `vendor/`.
  // Only refuse when there is neither, which means the pack produced nothing.
  if (fs.existsSync(TARGET)) process.exit(0);
  process.stderr.write("vendor.js: no " + SOURCE + " and no " + TARGET + "\n");
  process.exit(1);
}

fs.rmSync(path.join(HERE, "..", "vendor"), { recursive: true, force: true });
copy(SOURCE, TARGET);

const version = /__version__ = "([^"]+)"/.exec(
  fs.readFileSync(path.join(TARGET, "__init__.py"), "utf8"))[1];
const declared = JSON.parse(
  fs.readFileSync(path.join(HERE, "..", "package.json"), "utf8")).version;
if (version !== declared) {
  process.stderr.write(
    "vendor.js: package.json says " + declared + ", the Python says " + version + ".\n" +
    "FIX: set \"version\" in npm/package.json to " + version + " — the literal in " +
    "src/pagelore/__init__.py is the only place the version is decided.\n");
  process.exit(1);
}
process.stdout.write("vendored pagelore " + version + "\n");
