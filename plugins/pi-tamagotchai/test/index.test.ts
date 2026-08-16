import { describe, it, expect, beforeEach, vi } from "vitest";
import { mkdtempSync, readdirSync, readFileSync, rmSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

describe("factory wiring", () => {
  let dir: string;
  let handlers: Record<string, (e: any, ctx: any) => void>;
  let ctx: any;

  beforeEach(async () => {
    dir = mkdtempSync(join(tmpdir(), "tamagotchai-"));
    handlers = {};
    const pi: any = {
      on: (name: string, fn: (e: any, ctx: any) => void) => { handlers[name] = fn; },
    };
    ctx = {
      cwd: "/home/senpai/tamagotchai",
      sessionManager: { getSessionId: () => "sess-1" },
      model: { provider: "anthropic", id: "claude-3.7-sonnet" },
    };
    // point the extension at our temp dir
    process.env.TAMAGOTCHAI_SESSIONS_DIR = dir;
    // dynamic import so the factory captures the env at call time
    const mod = await import("../src/index");
    mod.default(pi);
  });

  it("session_start writes a file", () => {
    handlers["session_start"]({ reason: "startup" }, ctx);
    const files = readdirSync(dir);
    expect(files).toContain("sess-1.json");
    const st = JSON.parse(readFileSync(join(dir, "sess-1.json"), "utf8"));
    expect(st.status).toBe("working");
    expect(st.metadata.source).toBe("pi");
    expect(st.metadata.project).toBe("tamagotchai");
  });

  it("tool_execution_start then end update the file", () => {
    handlers["session_start"]({ reason: "startup" }, ctx);
    handlers["tool_execution_start"]({ type: "tool_execution_start", toolCallId: "t1", toolName: "bash", args: {} }, ctx);
    handlers["tool_execution_end"]({ type: "tool_execution_end", toolCallId: "t1", toolName: "bash", result: "", isError: false }, ctx);
    const st = JSON.parse(readFileSync(join(dir, "sess-1.json"), "utf8"));
    expect(st.metadata.tools_executed).toBe(1);
    expect(st.message).toBe("tool: bash");
  });

  it("message_end accumulates usage and model", () => {
    handlers["session_start"]({ reason: "startup" }, ctx);
    handlers["message_end"](
      { type: "message_end", message: { role: "assistant", usage: { input: 10, output: 5, totalTokens: 15, cost: { total: 0.01 } } } },
      ctx,
    );
    const st = JSON.parse(readFileSync(join(dir, "sess-1.json"), "utf8"));
    expect(st.metadata.tokens_total).toBe(15);
    expect(st.metadata.cost_usd).toBe(0.01);
    expect(st.metadata.model).toBe("anthropic/claude-3.7-sonnet");
  });

  it("agent_settled sets idle", () => {
    handlers["session_start"]({ reason: "startup" }, ctx);
    handlers["agent_settled"]({}, ctx);
    const st = JSON.parse(readFileSync(join(dir, "sess-1.json"), "utf8"));
    expect(st.status).toBe("idle");
    expect(st.pending).toBe(0);
  });

  it("session_shutdown deletes the file", () => {
    handlers["session_start"]({ reason: "startup" }, ctx);
    handlers["session_shutdown"]({ reason: "quit" }, ctx);
    expect(existsSync(join(dir, "sess-1.json"))).toBe(false);
  });

  it("ignores events when no session file exists (race)", () => {
    // no session_start yet
    handlers["tool_execution_start"]({ type: "tool_execution_start", toolCallId: "t1", toolName: "bash", args: {} }, ctx);
    expect(readdirSync(dir)).toEqual([]);
  });
});
