import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { appendFileSync } from "node:fs";

import {
  AgentState,
  applyEvent,
  atomicWrite,
  defaultState,
  deleteState,
  stateFilePath,
} from "./state";

const DEBUG = process.env.TAMAGOTCHAI_DEBUG === "1";
function log(msg: string): void {
  if (!DEBUG) return;
  try {
    appendFileSync(join(homedir(), ".local", "log", "pi-tamagotchai.log"), `${new Date().toISOString()} ${msg}\n`);
  } catch {
    // ignore
  }
}

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
    log(`event type=${event?.type} sid=${sid}`);
    if (!sid) return;
    const path = pathFor(sid);
    const prev = loadState(path);
    if (!prev) { log(`no prev state for ${sid}`); return; }
    const next = applyEvent(prev, event, ctx);
    atomicWrite(path, next);
    log(`-> status=${next.status} msg=${next.message}`);
  }

  pi.on("session_start", (_event: any, ctx: any) => {
    const sid = sessionId(ctx);
    log(`session_start sid=${sid}`);
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
    log(`session_shutdown sid=${sid}`);
    if (!sid) return;
    deleteState(pathFor(sid));
    paths.delete(sid);
  });

  // Periodic heartbeat: refresh last_heartbeat so daemon doesn't mark stale.
  // Also flips stuck "working" -> "idle" (safety net if turn_end/agent_settled
  // didn't fire). Fires every 30s per known session.
  setInterval(() => {
    for (const [sid, path] of paths) {
      const prev = loadState(path);
      if (!prev) continue;
      // Only heartbeat if last update was >25s ago (avoid spamming during active work)
      const ageMs = Date.now() - new Date(prev.last_heartbeat).getTime();
      if (ageMs < 25000) continue;
      const next = applyEvent(prev, { type: "heartbeat" }, {} as any);
      atomicWrite(path, next);
      log(`heartbeat sid=${sid} -> ${next.status}`);
    }
  }, 30000);
}
