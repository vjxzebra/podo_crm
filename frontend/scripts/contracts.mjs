import { mkdir, readFile, writeFile } from "node:fs/promises";
import openapiTS, { astToString } from "openapi-typescript";

const schemaUrl = new URL("../openapi/schema.json", import.meta.url);
const outputUrl = new URL("../src/api/schema.d.ts", import.meta.url);
const checking = process.argv.includes("--check");

const ast = await openapiTS(schemaUrl, { alphabetize: true });
const generated = [
  "// Generated from backend/openapi/schema.json. Do not edit by hand.",
  astToString(ast),
].join("\n");

if (checking) {
  const current = await readFile(outputUrl, "utf8").catch(() => "");
  if (current !== generated) {
    console.error("Generated API client is stale. Run scripts/update-contracts.");
    process.exitCode = 1;
  } else {
    console.log("Generated API client is current.");
  }
} else {
  await mkdir(new URL("../src/api/", import.meta.url), { recursive: true });
  await writeFile(outputUrl, generated, "utf8");
  console.log("Generated src/api/schema.d.ts.");
}
