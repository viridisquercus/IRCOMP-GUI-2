import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { test, after } from "node:test";

const web = fileURLToPath(new URL("../", import.meta.url));
const directory = mkdtempSync(join(tmpdir(), "ircomp-contracts-"));
after(() => rmSync(directory, { recursive: true, force: true }));
const compiled = spawnSync(
  join(web, "node_modules/.bin/tsc"),
  [
    "--ignoreConfig",
    "--target",
    "ES2022",
    "--module",
    "commonjs",
    "--strict",
    "--skipLibCheck",
    "--outDir",
    directory,
    join(web, "src/shared/api.ts"),
  ],
  { encoding: "utf8" },
);
assert.equal(compiled.status, 0, compiled.stdout + compiled.stderr);
const require = createRequire(import.meta.url);
/** @type {typeof import('../src/shared/responseValidation')} */
const { matchesSchema } = require(join(directory, "responseValidation.js"));
/** @type {typeof import('../src/shared/schemas.generated')} */
const { definitions, responseSchemas } = require(
  join(directory, "schemas.generated.js"),
);
/** @type {typeof import('../src/shared/api')} */
const { api, ApiError } = require(join(directory, "api.js"));

test("accepts a typed response and rejects missing nested fields", () => {
  assert.equal(
    matchesSchema({ studies: [] }, responseSchemas.StudyList, definitions),
    true,
  );
  assert.equal(
    matchesSchema(
      { studies: [{ study_id: 17 }] },
      responseSchemas.StudyList,
      definitions,
    ),
    false,
  );
});

test("checks dictionary values as well as ordinary object properties", () => {
  assert.equal(
    matchesSchema(
      { bad: 17 },
      definitions.StudyView.properties?.target_labels ?? {},
      definitions,
    ),
    false,
  );
});

test("the HTTP helper rejects invalid successful response bodies", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ studies: [{ title: 17 }] }));
    await assert.rejects(
      () => api("/studies", "StudyList"),
      (error) => error instanceof ApiError && error.code === "RESPONSE_INVALID",
    );
    globalThis.fetch = async () => new Response("not json");
    await assert.rejects(
      () => api("/studies", "StudyList"),
      (error) => error instanceof ApiError && error.code === "RESPONSE_INVALID",
    );
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ studies: [] }));
    assert.deepEqual(await api("/studies", "StudyList"), { studies: [] });
  } finally {
    globalThis.fetch = original;
  }
});

test("the HTTP helper preserves valid application errors", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () =>
      new Response(
        JSON.stringify({
          error: {
            code: "NOT_FOUND",
            message: "Missing study",
            diagnostics: [],
          },
        }),
        { status: 404 },
      );
    await assert.rejects(
      () => api("/studies", "StudyList"),
      (error) => error instanceof ApiError && error.code === "NOT_FOUND",
    );
  } finally {
    globalThis.fetch = original;
  }
});
