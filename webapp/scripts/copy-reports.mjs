#!/usr/bin/env node
// copy-reports.mjs — copies .ai/reports/*.json into src/data/reports/
// Run before `vite dev` or `vite build` to embed the latest reports.
// <!-- version: 1.0.0 -->

import { cpSync, mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const src = resolve(__dirname, "../../.ai/reports");
const dest = resolve(__dirname, "../src/data/reports");

mkdirSync(dest, { recursive: true });
cpSync(src, dest, { recursive: true, filter: (f) => f.endsWith(".json") || f === src });

console.log(`reports: copied ${src} → ${dest}`);
