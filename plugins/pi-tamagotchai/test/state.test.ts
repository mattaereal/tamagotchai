import { describe, it, expect } from "vitest";
import { applyEvent, defaultState, extractUsage, stateFilePath } from "../src/state";

describe("defaultState", () => {
  it("starts working with source pi", () => {
    const s = defaultState("tamagotchai");
    expect(s.status).toBe("working");
    expect(s.message).toBe("session started");
    expect(s.metadata.source).toBe("pi");
    expect(s.metadata.project).toBe("tamagotchai");
  });
});

describe("applyEvent", () => {
  it("tool_execution_start sets working + tool_name + message", () => {
    const s = defaultState("p");
    const out = applyEvent(s, { type: "tool_execution_start", toolCallId: "t1", toolName: "bash", args: {} }, {});
    expect(out.status).toBe("working");
    expect(out.message).toBe("tool: bash");
    expect(out.metadata.tool_name).toBe("bash");
  });

  it("tool_execution_end error sets status error", () => {
    const s = defaultState("p");
    const mid = applyEvent(s, { type: "tool_execution_start", toolCallId: "t1", toolName: "bash", args: {} }, {});
    const out = applyEvent(mid, { type: "tool_execution_end", toolCallId: "t1", toolName: "bash", result: "", isError: true }, {});
    expect(out.status).toBe("error");
    expect(out.metadata.tools_executed).toBe(1);
  });

  it("tool_execution_end success keeps working and counts", () => {
    const s = defaultState("p");
    const mid = applyEvent(s, { type: "tool_execution_start", toolCallId: "t1", toolName: "bash", args: {} }, {});
    const out = applyEvent(mid, { type: "tool_execution_end", toolCallId: "t1", toolName: "bash", result: "", isError: false }, {});
    expect(out.status).toBe("working");
    expect(out.metadata.tools_executed).toBe(1);
  });

  it("turn_start increments turn_count", () => {
    const s = defaultState("p");
    const out = applyEvent(s, { type: "turn_start", turnIndex: 0, timestamp: 0 }, {});
    expect(out.metadata.turn_count).toBe(1);
  });

  it("agent_settled sets idle", () => {
    const s = defaultState("p");
    const out = applyEvent(s, { type: "agent_settled" }, {});
    expect(out.status).toBe("idle");
    expect(out.message).toBe("settled");
  });

  it("message_end accumulates usage and model", () => {
    let s = defaultState("p");
    s = applyEvent(s, { type: "message_end", message: { role: "assistant", usage: { input: 10, output: 5, totalTokens: 15, cost: { total: 0.01 } } } }, { model: { provider: "anthropic", id: "claude-3.7-sonnet" } });
    expect(s.metadata.tokens_input).toBe(10);
    expect(s.metadata.tokens_output).toBe(5);
    expect(s.metadata.tokens_total).toBe(15);
    expect(s.metadata.cost_usd).toBe(0.01);
    expect(s.metadata.model).toBe("anthropic/claude-3.7-sonnet");
  });

  it("before_agent_start truncates prompt into message", () => {
    const s = defaultState("p");
    const out = applyEvent(s, { type: "before_agent_start", prompt: "x".repeat(80) }, {});
    expect(out.message.length).toBeLessThanOrEqual(60);
  });

  it("unknown event returns state unchanged", () => {
    const s = defaultState("p");
    const out = applyEvent(s, { type: "whatever" }, {});
    expect(out).toBe(s);
  });
});

describe("extractUsage", () => {
  it("returns null when no usage", () => {
    expect(extractUsage({ role: "assistant" })).toBeNull();
  });
  it("maps fields", () => {
    const u = extractUsage({ usage: { input: 1, output: 2, totalTokens: 3, cost: { total: 0.5 } } });
    expect(u).toEqual({ tokens_input: 1, tokens_output: 2, tokens_total: 3, cost_usd: 0.5 });
  });
});

describe("stateFilePath", () => {
  it("joins dir + id + json", () => {
    expect(stateFilePath("/tmp/s", "abc")).toBe("/tmp/s/abc.json");
  });
});