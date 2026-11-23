import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

import { build } from "esbuild";

let sources;
let directory;

test.before(async () => {
  directory = await mkdtemp(path.join(tmpdir(), "presenton-image-sources-"));
  const outfile = path.join(directory, "image-sources.mjs");
  await build({
    entryPoints: [
      path.resolve("components/slide-editor/images/image-sources.ts"),
    ],
    outfile,
    bundle: true,
    platform: "node",
    format: "esm",
    tsconfig: path.resolve("tsconfig.json"),
    logLevel: "silent",
  });
  sources = await import(pathToFileURL(outfile).href);
});

test.after(async () => {
  if (directory) await rm(directory, { recursive: true, force: true });
});

test("ai provider plus stock key offers both and defaults to ai", () => {
  const resolved = sources.resolveImageSources({
    IMAGE_PROVIDER: "gemini_flash",
    PEXELS_API_KEY: "pexels-key",
  });
  assert.deepEqual(resolved.availableSources, ["stock", "ai"]);
  assert.equal(resolved.defaultSource, "ai");
  assert.equal(resolved.stockProvider, "pexels");
  assert.equal(resolved.stockApiKey, "pexels-key");
  assert.equal(resolved.aiProvider, "gemini_flash");
});

test("stock provider keeps generation out even with an ai-style key", () => {
  const resolved = sources.resolveImageSources({
    IMAGE_PROVIDER: "pixabay",
    PIXABAY_API_KEY: "pixabay-key",
    PEXELS_API_KEY: "pexels-key",
  });
  assert.deepEqual(resolved.availableSources, ["stock"]);
  assert.equal(resolved.defaultSource, "stock");
  assert.equal(resolved.stockProvider, "pixabay");
  assert.equal(resolved.aiAvailable, false);
  assert.equal(resolved.aiBlockedReason, "stock-provider");
});

test("stock stays available without a client key", () => {
  const resolved = sources.resolveImageSources({ IMAGE_PROVIDER: "pexels" });
  assert.equal(resolved.stockAvailable, true);
  assert.equal(resolved.stockApiKey, null);
});

test("disabled generation leaves stock as the only source", () => {
  const resolved = sources.resolveImageSources({
    IMAGE_PROVIDER: "gpt-image-2",
    DISABLE_IMAGE_GENERATION: true,
    PEXELS_API_KEY: "pexels-key",
  });
  assert.deepEqual(resolved.availableSources, ["stock"]);
  assert.equal(resolved.aiBlockedReason, "disabled");
});

test("no configuration offers nothing", () => {
  const resolved = sources.resolveImageSources({});
  assert.deepEqual(resolved.availableSources, []);
  assert.equal(resolved.defaultSource, null);
});

test("provider aliases resolve to pexels", () => {
  assert.equal(sources.normalizeImageProvider("Pixels"), "pexels");
  assert.equal(sources.isStockProviderId("pexel"), true);
  assert.equal(sources.isStockProviderId("gpt-image-1.5"), false);
});
