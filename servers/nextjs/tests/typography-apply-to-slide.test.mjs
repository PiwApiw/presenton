import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

import { build } from "esbuild";

let module_;
let directory;

test.before(async () => {
  directory = await mkdtemp(path.join(tmpdir(), "presenton-apply-"));
  const outfile = path.join(directory, "apply.mjs");
  await build({
    entryPoints: [path.resolve("components/typography/apply-to-slide.ts")],
    outfile,
    bundle: true,
    platform: "node",
    format: "esm",
    tsconfig: path.resolve("tsconfig.json"),
    logLevel: "silent",
  });
  module_ = await import(pathToFileURL(outfile).href);
});

test.after(async () => {
  if (directory) await rm(directory, { recursive: true, force: true });
});

function layout() {
  return {
    elements: [
      { type: "text", name: "slide_title", font: { family: "Arial", size: 48 } },
      { type: "text", name: "slide_subtitle", font: { family: "Arial", size: 32 } },
      { type: "text", name: "body_copy", font: { family: "Arial", size: 18 } },
      { type: "image", name: "hero", font: { size: 999 } },
    ],
  };
}

test("assigns roles by size and overrides family and size", () => {
  const result = module_.applyTypographyToSlide(layout(), {
    roles: { title: { family: "Inter", size: 52 }, body: { size: 16 } },
  });
  assert.equal(result.elements[0].font.family, "Inter");
  assert.equal(result.elements[0].font.size, 52);
  assert.equal(result.elements[1].font.size, 32);
  assert.equal(result.elements[2].font.size, 16);
  assert.equal(result.elements[3].font.size, 999);
});

test("manual fonts are never overridden", () => {
  const input = layout();
  input.elements[0].font.manual = true;
  const result = module_.applyTypographyToSlide(input, {
    roles: { title: { family: "Inter", size: 52 } },
  });
  assert.equal(result.elements[0].font.family, "Arial");
  assert.equal(result.elements[0].font.size, 48);
});

test("label-like elements never become title", () => {
  const input = {
    elements: [
      { type: "text", name: "footer_label", font: { size: 60 } },
      { type: "text", name: "heading", font: { size: 40 } },
    ],
  };
  const result = module_.applyTypographyToSlide(input, {
    roles: { title: { size: 52 } },
  });
  assert.equal(result.elements[0].font.size, 60);
  assert.equal(result.elements[1].font.size, 52);
});

test("run sizes scale with the base size change", () => {
  const input = {
    elements: [
      {
        type: "text",
        name: "heading",
        font: { size: 40 },
        runs: [{ font: { size: 20 } }],
      },
    ],
  };
  const result = module_.applyTypographyToSlide(input, {
    roles: { title: { size: 80 } },
  });
  assert.equal(result.elements[0].font.size, 80);
  assert.equal(result.elements[0].runs[0].font.size, 40);
});