import { writeFileSync, renameSync, unlinkSync, existsSync } from "node:fs";
import { join } from "node:path";

export interface AgentState {
  status: string;
  message: string;
  last_heartbeat: string;
  pending: number;
  metadata: {
    project?: string;
    model?: string;
    tool_name?: string;
    turn_count?: number;
    tools_executed?: number;
    tokens_input?: number;
    tokens_output?: number;
    tokens_total?: number;
    cost_usd?: number;
    session_duration_ms?: number;
    source: "pi";
  };
}

function nowIso(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

export function defaultState(project: string): AgentState {
  return {
    status: "working",
    message: "session started",
    last_heartbeat: nowIso(),
    pending: 1,
    metadata: { project, source: "pi", turn_count: 0, tools_executed: 0, tokens_input: 0, tokens_output: 0, tokens_total: 0, cost_usd: 0 },
  };
}

export function extractUsage(message: any): { tokens_input: number; tokens_output: number; tokens_total: number; cost_usd: number } | null {
  const u = message?.usage;
  if (!u) return null;
  return {
    tokens_input: Number(u.input ?? 0),
    tokens_output: Number(u.output ?? 0),
    tokens_total: Number(u.totalTokens ?? 0),
    cost_usd: Number(u?.cost?.total ?? 0),
  };
}

export function applyEvent(state: AgentState, event: { type: string; [k: string]: any }, ctx: { cwd?: string; model?: { provider?: string; id?: string } }): AgentState {
  const next: AgentState = { ...state, metadata: { ...state.metadata } };
  switch (event.type) {
    case "session_start":
      next.status = "working";
      next.message = "session started";
      next.metadata.project = ctx?.cwd?.split("/").pop() || state.metadata.project;
      break;
    case "before_agent_start":
      next.status = "working";
      next.message = String(event.prompt ?? "").slice(0, 60);
      break;
    case "tool_execution_start":
      next.status = "working";
      next.message = `tool: ${event.toolName}`;
      next.metadata.tool_name = event.toolName;
      break;
    case "tool_execution_end": {
      next.metadata.tools_executed = (state.metadata.tools_executed ?? 0) + 1;
      next.status = event.isError ? "error" : "working";
      next.message = `tool: ${event.toolName}`;
      break;
    }
    case "turn_start":
      next.metadata.turn_count = (state.metadata.turn_count ?? 0) + 1;
      next.status = "working";
      next.message = "thinking";
      next.pending = 1;
      break;
    case "turn_end":
      // Turn done = waiting for user input
      next.status = "idle";
      next.message = "waiting";
      next.pending = 0;
      break;
    case "message_end": {
      const u = extractUsage(event.message);
      if (u) {
        next.metadata.tokens_input = (state.metadata.tokens_input ?? 0) + u.tokens_input;
        next.metadata.tokens_output = (state.metadata.tokens_output ?? 0) + u.tokens_output;
        next.metadata.tokens_total = (state.metadata.tokens_total ?? 0) + u.tokens_total;
        next.metadata.cost_usd = Number(((state.metadata.cost_usd ?? 0) + u.cost_usd).toFixed(4));
      }
      if (ctx?.model) next.metadata.model = `${ctx.model.provider ?? ""}/${ctx.model.id ?? ""}`.replace(/^\//, "");
      break;
    }
    case "agent_settled":
      next.status = "idle";
      next.message = "settled";
      next.pending = 0;
      break;
    case "heartbeat":
      // Just refresh last_heartbeat; keep current status
      next.status = state.status === "working" ? "idle" : state.status;
      next.message = state.status === "working" ? "waiting" : state.message;
      next.pending = state.status === "working" ? 0 : state.pending;
      break;
    default:
      return state;
  }
  next.last_heartbeat = nowIso();
  return next;
}

export function stateFilePath(sessionsDir: string, sessionId: string): string {
  return join(sessionsDir, `${sessionId}.json`);
}

export function atomicWrite(path: string, state: AgentState): void {
  const tmp = `${path}.tmp`;
  writeFileSync(tmp, JSON.stringify(state));
  renameSync(tmp, path);
}

export function deleteState(path: string): void {
  try { unlinkSync(path); } catch (e: any) { if (e.code !== "ENOENT") throw e; }
}

export function heartbeat(state: AgentState): AgentState {
  return { ...state, last_heartbeat: nowIso() };
}

export { existsSync };