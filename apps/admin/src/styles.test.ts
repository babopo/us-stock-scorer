import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const styles = readFileSync("src/styles.css", "utf8");
const indexHtml = readFileSync("index.html", "utf8");

describe("admin responsive styles", () => {
  it("keeps the main layout full width when the desktop sider is removed below 760px", () => {
    expect(styles).toMatch(/@media\s*\(max-width:\s*760px\)[\s\S]*\.admin-layout\s*>\s*\.admin-main-layout\s*\{[\s\S]*width:\s*100%\s*!important;/);
    expect(styles).toMatch(/@media\s*\(max-width:\s*760px\)[\s\S]*\.admin-layout\s*>\s*\.admin-main-layout\s*\{[\s\S]*flex:\s*1\s+1\s+100%;/);
    expect(styles).toMatch(/\.admin-header\s*\{[\s\S]*line-height:\s*1\.2;/);
  });
});

describe("admin shell metadata", () => {
  it("disables mobile viewport zoom to keep input focus from enlarging the page", () => {
    expect(indexHtml).toMatch(/<meta\s+name="viewport"\s+content="[^"]*maximum-scale=1\.0[^"]*"/);
    expect(indexHtml).toMatch(/<meta\s+name="viewport"\s+content="[^"]*user-scalable=no[^"]*"/);
  });
});
