import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";

const repoRoot = process.cwd();

function readRepoFile(filePath: string): string {
  return readFileSync(path.join(repoRoot, filePath), "utf8");
}

test("active workspace no longer includes the WeChat Mini Program frontend", () => {
  assert.equal(existsSync(path.join(repoRoot, "apps/miniprogram")), false);

  const rootPackage = JSON.parse(readRepoFile("package.json")) as {
    scripts?: Record<string, string>;
    workspaces?: string[];
    devDependencies?: Record<string, string>;
  };

  assert.equal(rootPackage.workspaces?.includes("apps/miniprogram"), false);
  assert.equal(Boolean(rootPackage.devDependencies?.["miniprogram-api-typings"]), false);

  const rootScripts = Object.values(rootPackage.scripts || {}).join("\n");
  assert.match(rootScripts, /packages\/api-client/);
  assert.doesNotMatch(rootScripts, /miniprogram/);

  assert.doesNotMatch(readRepoFile("pnpm-workspace.yaml"), /miniprogram/);
});

test("api client only exposes the web fetch transport", () => {
  assert.equal(existsSync(path.join(repoRoot, "packages/api-client/src/transports/wx.ts")), false);

  const publicExports = readRepoFile("packages/api-client/src/index.ts");

  assert.match(publicExports, /createFetchTransport/);
  assert.doesNotMatch(publicExports, /createWxTransport|WxRequestApi|transports\/wx/);
});
