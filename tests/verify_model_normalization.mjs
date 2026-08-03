import { readFileSync } from "node:fs";
import { normalizeModelCode } from "../config/model_normalization.mjs";

const fixturePath = process.argv[2];
if (!fixturePath) throw new Error("fixture path is required");
const fixtures = JSON.parse(readFileSync(fixturePath, "utf8"));
for (const fixture of fixtures) {
  const actual = normalizeModelCode(fixture.input);
  if (actual !== fixture.normalized) {
    throw new Error(`${JSON.stringify(fixture.input)}: ${actual} != ${fixture.normalized}`);
  }
}
process.stdout.write(JSON.stringify({ verified: fixtures.length }) + "\n");
