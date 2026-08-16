import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

import {
  AgentState,
  applyEvent,
  atomicWrite,
  defaultState,
  deleteState,
  stateFilePath,
} from "./state";

/**
 * Minimal pi ExtensionAPI surface used by this extension.
 * The real type is exported by @earendil-works/pi-coding-agent; we only need
 * `on(eventName, handler)` here. Declared locally to avoid a hard runtime dep
 * on the pi package at type-check time.
 */
export interface ExtensionAPI {
  on(event: string, handler: (event: any, ctx: any) => void): void;
}

function sessionsDir(): string {
  return (
    process.env.TAMAGOTCHAI_SESSIONS_DIR ||
    join(homedir(), ".pi", "agent", "tamagotchai", "sessions")
  );
}

function loadState(path: string): AgentState | null {
  try {
    return JSON.parse(readFileSync(path, "utf8")) as AgentState;
  } catch {
    return null;
  }
}

export default function (pi: ExtensionAPI): void {
  // session id -> state file path. Survives reloads within one process.
  const paths = new Map<string, string>();

  function pathFor(sessionId: string): string {
    let p = paths.get(sessionId);
    if (!p) {
      p = stateFilePath(sessionsDir(), sessionId);
      paths.set(sessionId, p);
    }
    return p;
  }

  function sessionId(ctx: any): string | null {
    const sid = ctx?.sessionManager?.getSessionId?.();
    return sid ? String(sid) : null;
  }

  function withState(event: any, ctx: any): void {
    const sid = sessionId(ctx);
    if (!sid) return;
    const path = pathFor(sid);
    const prev = loadState(path);
    if (!prev) return; // race: no session_start seen yet
    atomicWrite(path, applyEvent(prev, event, ctx));
  }

  pi.on("session_start", (_event: any, ctx: any) => {
    const sid = sessionId(ctx);
    if (!sid) return;
    const project = ctx?.cwd?.split("/").pop() || "unknown";
    atomicWrite(pathFor(sid), defaultState(project));
  });

  pi.on("before_agent_start", (event: any, ctx: any) =>
    withState({ ...event, type: "before_agent_start" }, ctx),
  );
  pi.on("tool_execution_start", (event: any, ctx: any) => withState(event, ctx));
  pi.on("tool_execution_end", (event: any, ctx: any) => withState(event, ctx));
  pi.on("turn_start", (event: any, ctx: any) => withState(event, ctx));
  pi.on("turn_end", (event: any, ctx: any) => withState(event, ctx));
  pi.on("message_end", (event: any, ctx: any) => withState(event, ctx));
  pi.on("agent_settled", (_event: any, ctx: any) =>
    withState({ type: "agent_settled" }, ctx),
  );

  pi.on("session_shutdown", (_event: any, ctx: any) => {
    const sid = sessionId(ctx);
    if (!sid) return;
    deleteState(pathFor(sid));
    paths.delete(sid);
  });
}
