import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

import { build } from "esbuild";

let typography;
let directory;

test.before(async () => {
  directory = await mkdtemp(path.join(tmpdir(), "presenton-typography-"));
  const outfile = path.join(directory, "effective.mjs");
  await build({
    entryPoints: [path.resolve("components/typography/effective.ts")],
    outfile,
    bundle: true,
    platform: "node",
    format: "esm",
    tsconfig: path.resolve("tsconfig.json"),
    logLevel: "silent",
  });
  typography = await import(pathToFileURL(outfile).href);
});

test.after(async () => {
  if (directory) await rm(directory, { recursive: true, force: true });
});

test("slide overrides merge per field over presentation values", () => {
  const resolved = typography.resolveTypography(
    { roles: { title: { family: "Inter", size: 52 }, body: { size: 18 } } },
    { roles: { title: { size: 40 } } },
  );
  assert.equal(resolved.roles.title.family, "Inter");
  assert.equal(resolved.roles.title.size, 40);
  assert.equal(resolved.roles.body.size, 18);
  assert.equal(resolved.roles.subtitle.size, null);
});

test("empty config is auto", () => {
  assert.equal(typography.isAutoTypography(null), true);
  assert.equal(
    typography.isAutoTypography(typography.resolveTypography(null, null)),
    true,
  );
  assert.equal(
    typography.isAutoTypography({ roles: { title: { size: 52 } } }),
    false,
  );
});

test("css only contains filled roles and uses important", () => {
  const css = typography.typographyStyleCss({
    roles: { title: { family: "Inter", size: 52 }, body: { size: 18 } },
  });
  assert.match(css, /\[data-text-role="title"\]/);
  assert.match(css, /font-size:52px !important/);
  assert.match(css, /font-size:18px !important/);
  assert.doesNotMatch(css, /data-text-role="subtitle"/);
  assert.equal(typography.typographyStyleCss(null), "");
});

test("scoping prefixes every rule with the slide container", () => {
  const css = typography.typographyStyleCss({
    roles: { title: { size: 52 }, body: { size: 18 } },
  });
  const scoped = typography.scopeTypographyCss(css, '#slide-3');
  const rules = scoped.split("\n");
  assert.equal(rules.length, 2);
  for (const rule of rules) {
    assert.match(rule, /^#slide-3 section\[data-slide-type\] /);
  }
  assert.match(scoped, /font-size:52px !important/);
  assert.equal(typography.scopeTypographyCss("", '#slide-3'), "");
});
