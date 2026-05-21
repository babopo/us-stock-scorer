# TypeScript Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert all JavaScript source and tests in the mini program and shared API client to TypeScript with strict, runnable type checks.

**Architecture:** `packages/api-client` becomes a TypeScript package that compiles to CommonJS in `dist/` for mini program consumption. `apps/miniprogram` uses native WeChat TypeScript compiler support, local `tsc --noEmit` for type checking, and typed access to `wx`, `Page`, `App`, and the shared client.

**Tech Stack:** TypeScript, Node test runner, `tsx`, `miniprogram-api-typings`, WeChat `useCompilerPlugins: ["typescript"]`.

---

### Task 1: Tooling And Type Check Baseline

**Files:**
- Modify: `package.json`
- Modify: `packages/api-client/package.json`
- Modify: `apps/miniprogram/package.json`
- Create: `tsconfig.json`
- Create: `packages/api-client/tsconfig.json`
- Create: `apps/miniprogram/tsconfig.json`

- [ ] **Step 1: Add TypeScript tooling and scripts**

Add root scripts:

```json
{
  "scripts": {
    "build": "pnpm --filter @stock-scorer/api-client build",
    "test": "pnpm --filter @stock-scorer/api-client build && node --import tsx --test packages/api-client/test/*.test.ts apps/miniprogram/pages/index/*.test.ts",
    "typecheck": "tsc -b packages/api-client apps/miniprogram"
  }
}
```

Add `typescript`, `tsx`, `@types/node`, and `miniprogram-api-typings` as dev dependencies.

- [ ] **Step 2: Run baseline type check**

Run: `pnpm typecheck`

Expected: FAIL because the referenced TypeScript files and declarations do not exist yet.

### Task 2: API Client TypeScript Package

**Files:**
- Rename: `packages/api-client/src/*.js` to `.ts`
- Rename: `packages/api-client/test/client.test.js` to `.ts`
- Modify: `packages/api-client/package.json`

- [ ] **Step 1: Convert API client modules**

Use explicit exported types for `HttpMethod`, `ApiRequest`, `ApiResponse`, `ApiTransport`, `ApiErrorCode`, `StockScore`, `ProviderStatus`, `TickerRawData`, `ScoreSnapshots`, `StockScorerClient`, and client options.

- [ ] **Step 2: Run API client build and tests**

Run: `pnpm --filter @stock-scorer/api-client build && node --import tsx --test packages/api-client/test/client.test.ts`

Expected: PASS with existing client behavior preserved.

### Task 3: Mini Program TypeScript Source

**Files:**
- Rename: `apps/miniprogram/app.js` to `.ts`
- Rename: `apps/miniprogram/utils/api.js` to `.ts`
- Rename: `apps/miniprogram/pages/index/factor-radar.js` to `.ts`
- Rename: `apps/miniprogram/pages/index/index.js` to `.ts`
- Rename: `apps/miniprogram/pages/index/factor-radar.test.js` to `.ts`
- Create: `apps/miniprogram/types/app.ts`

- [ ] **Step 1: Convert app and utility modules**

Type global app data, mini program API creation, API error message mapping, radar factor geometry, and page data/methods.

- [ ] **Step 2: Run mini program type check and tests**

Run: `pnpm typecheck && node --import tsx --test apps/miniprogram/pages/index/*.test.ts`

Expected: PASS with radar behavior preserved.

### Task 4: Mini Program Compiler Configuration And Documentation

**Files:**
- Modify: `apps/miniprogram/project.config.json`
- Modify: `README.md`

- [ ] **Step 1: Enable native TypeScript compiler plugin**

Set `setting.useCompilerPlugins` to `["typescript"]`, keep no same-name generated JS files, and document that local type errors are caught by `pnpm typecheck`.

- [ ] **Step 2: Run final verification**

Run:

```bash
pnpm build
pnpm typecheck
pnpm test
rg --files -g '*.js' -g '!node_modules' -g '!packages/api-client/dist/**'
```

Expected: build/typecheck/tests pass. The remaining `.js` files, if any, are generated build output only.
