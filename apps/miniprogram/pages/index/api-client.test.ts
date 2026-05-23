import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import * as ts from "typescript";

import { createMiniProgramApiClient } from "../../utils/api";

const MINIPROGRAM_ROOT = path.resolve(process.cwd(), "apps/miniprogram");

function getTypeScriptFiles(directory: string): string[] {
  return readdirSync(directory).flatMap((entry) => {
    if (entry === "node_modules" || entry === "miniprogram_npm") {
      return [];
    }

    const filePath = path.join(directory, entry);
    const stats = statSync(filePath);
    if (stats.isDirectory()) {
      return getTypeScriptFiles(filePath);
    }

    return filePath.endsWith(".ts") ? [filePath] : [];
  });
}

test("mini program sources only use api-client as a type-only import", () => {
  for (const filePath of getTypeScriptFiles(MINIPROGRAM_ROOT)) {
    const sourceText = readFileSync(filePath, "utf8");
    const sourceFile = ts.createSourceFile(filePath, sourceText, ts.ScriptTarget.Latest, true);

    for (const statement of sourceFile.statements) {
      if (
        ts.isImportDeclaration(statement) &&
        ts.isStringLiteral(statement.moduleSpecifier) &&
        statement.moduleSpecifier.text === "@stock-scorer/api-client" &&
        !statement.importClause?.isTypeOnly
      ) {
        assert.fail(`${path.relative(MINIPROGRAM_ROOT, filePath)} imports @stock-scorer/api-client at runtime`);
      }
    }
  }
});

test("createMiniProgramApiClient sends the configured read token", async () => {
  const previousWx = (globalThis as typeof globalThis & { wx?: unknown }).wx;
  const requests: Array<{ header?: Record<string, string> }> = [];

  (globalThis as typeof globalThis & { wx: unknown }).wx = {
    request(options: {
      header?: Record<string, string>;
      success(response: { statusCode: number; header: Record<string, string>; data: unknown }): void;
    }) {
      requests.push(options);
      options.success({
        statusCode: 200,
        header: {},
        data: {
          ticker: "MSFT",
          company_name: "Microsoft Corporation",
          last_price: 420.5,
          medium_term_score: 82,
          medium_term_label: "positive",
          short_term_score: 74,
          short_term_label: "probe",
          factors: [],
          decision: {
            action: "small_probe",
            summary: "小仓试探",
            trigger_conditions: [],
            invalidation_conditions: [],
            risks: []
          },
          data_as_of: "2026-05-23",
          data_source: "fixture"
        }
      });
    }
  };

  try {
    const client = createMiniProgramApiClient("http://127.0.0.1:8000", "read-token");
    await client.getStockScore("msft");
  } finally {
    (globalThis as typeof globalThis & { wx?: unknown }).wx = previousWx;
  }

  assert.equal(requests[0]?.header?.authorization, "Bearer read-token");
});
