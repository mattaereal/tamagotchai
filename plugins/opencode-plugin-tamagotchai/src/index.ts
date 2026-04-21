import http from "http"

const PORT = parseInt(process.env.TAMAGOTCHAI_PORT ?? "7788", 10)
const HOST = process.env.TAMAGOTCHAI_HOST ?? "0.0.0.0"

let server = null
let logFn = null

function nowIso() {
  return new Date().toISOString()
}

function log(level, message, extra) {
  const entry = { service: "opencode-plugin-tamagotchai", level, message, extra }
  if (logFn) {
    try { logFn({ body: entry }) } catch {}
  } else {
    console.log(`[${level}] ${message}`, extra || "")
  }
}

// ---- per-session state ----
const sessions = new Map() // sessionID -> SessionState
let projectName = ""
let latestSessionID = "" // most recently active session

function getOrCreateSession(sessionID) {
  if (!sessions.has(sessionID)) {
    sessions.set(sessionID, {
      status: "idle",
      message: "",
      last_heartbeat: nowIso(),
      pending: 0,
      metadata: {},
      start_time: Date.now(),
      message_count: 0,
      files_modified: new Set(),
    })
  }
  return sessions.get(sessionID)
}

function updateSessionHeartbeat(sessionID) {
  const s = getOrCreateSession(sessionID)
  s.last_heartbeat = nowIso()
}

function setSessionStatus(sessionID, status, msg) {
  const s = getOrCreateSession(sessionID)
  s.status = status
  if (msg !== undefined) s.message = msg
  updateSessionHeartbeat(sessionID)
  latestSessionID = sessionID
}

function setWorking(sessionID, msg) {
  const s = getOrCreateSession(sessionID)
  s.status = "working"
  s.pending = Math.max(1, s.pending)
  if (msg) s.message = msg
  updateSessionHeartbeat(sessionID)
  latestSessionID = sessionID
}

function setIdle(sessionID) {
  const s = getOrCreateSession(sessionID)
  s.status = "idle"
  s.pending = 0
  s.message = ""
  updateSessionHeartbeat(sessionID)
}

function setError(sessionID, msg) {
  const s = getOrCreateSession(sessionID)
  s.status = "error"
  s.pending = 0
  if (msg) s.message = msg
  updateSessionHeartbeat(sessionID)
  latestSessionID = sessionID
}

function setSuccess(sessionID, msg) {
  const s = getOrCreateSession(sessionID)
  s.status = "success"
  s.pending = 0
  if (msg) s.message = msg
  updateSessionHeartbeat(sessionID)
  latestSessionID = sessionID
}

function computeSessionDuration(sessionID) {
  const s = sessions.get(sessionID)
  if (!s || !s.start_time) return undefined
  return Date.now() - s.start_time
}

function stripNulls(obj) {
  const out = {}
  for (const [k, v] of Object.entries(obj)) {
    if (v === null || v === undefined) continue
    if (typeof v === "number" && Number.isNaN(v)) continue
    out[k] = v
  }
  return out
}

function buildMetadata(session) {
  const meta = { ...session.metadata }
  if (projectName) meta.project = projectName
  if (session.message_count > 0) meta.message_count = session.message_count
  if (session.files_modified.size > 0) meta.files_modified = session.files_modified.size
  return stripNulls(meta)
}

function sessionToPayload(sessionID) {
  const s = sessions.get(sessionID)
  if (!s) return null
  const meta = buildMetadata(s)
  const duration = computeSessionDuration(sessionID)
  if (duration !== undefined && s.status !== "idle") {
    meta.session_duration_ms = duration
  }
  return {
    session_id: sessionID,
    status: s.status,
    message: s.message,
    last_heartbeat: s.last_heartbeat,
    pending: s.pending,
    metadata: meta,
  }
}

function getLatestActivePayload() {
  // If we have a latestSessionID that exists, use it
  if (latestSessionID && sessions.has(latestSessionID)) {
    const s = sessions.get(latestSessionID)
    if (s.status !== "idle") return sessionToPayload(latestSessionID)
  }
  // Otherwise find the most recently heartbeated non-idle session
  let best = null
  let bestTime = 0
  for (const [sid, s] of sessions.entries()) {
    if (s.status === "idle") continue
    const t = new Date(s.last_heartbeat).getTime()
    if (t > bestTime) {
      bestTime = t
      best = sid
    }
  }
  if (best) return sessionToPayload(best)
  // Fallback: most recent idle session
  for (const [sid, s] of sessions.entries()) {
    const t = new Date(s.last_heartbeat).getTime()
    if (t > bestTime) {
      bestTime = t
      best = sid
    }
  }
  return best ? sessionToPayload(best) : null
}

function getAllPayloads() {
  const list = []
  for (const sid of sessions.keys()) {
    list.push(sessionToPayload(sid))
  }
  // Sort by most recently active first
  list.sort((a, b) => new Date(b.last_heartbeat).getTime() - new Date(a.last_heartbeat).getTime())
  return list
}

function getAggregatedPayload() {
  const all = getAllPayloads()
  if (all.length === 0) {
    return {
      status: "idle",
      message: "no sessions",
      last_heartbeat: nowIso(),
      pending: 0,
      metadata: { sessions_total: 0, sessions_active: 0 },
    }
  }

  let costTotal = 0
  let tokIn = 0
  let tokOut = 0
  let tokTotal = 0
  let filesTotal = 0
  let msgsTotal = 0
  let activeCount = 0
  const models = new Set()
  const toolSet = new Set()

  for (const s of all) {
    if (s.status !== "idle") activeCount++
    const m = s.metadata || {}
    if (m.cost_usd) costTotal += m.cost_usd
    if (m.tokens_input) tokIn += m.tokens_input
    if (m.tokens_output) tokOut += m.tokens_output
    if (m.tokens_total) tokTotal += m.tokens_total
    if (m.files_modified) filesTotal += m.files_modified
    if (m.message_count) msgsTotal += m.message_count
    if (m.model) models.add(m.model)
    if (m.tool_name) toolSet.add(m.tool_name)
  }

  const latest = all[0]
  const meta = {
    sessions_total: all.length,
    sessions_active: activeCount,
    cost_usd_total: parseFloat(costTotal.toFixed(6)),
    tokens_input_total: tokIn,
    tokens_output_total: tokOut,
    tokens_total_total: tokTotal,
    files_modified_total: filesTotal,
    message_count_total: msgsTotal,
    models: Array.from(models),
    tools: Array.from(toolSet),
    latest_session_id: latest.session_id,
  }

  // Trim nulls
  const cleanMeta = stripNulls(meta)

  return {
    status: activeCount > 0 ? "working" : "idle",
    message: activeCount > 0
      ? `${activeCount} active / ${all.length - activeCount} idle`
      : `${all.length} idle`,
    last_heartbeat: latest.last_heartbeat,
    pending: activeCount,
    metadata: cleanMeta,
  }
}

function extractPartTokens(event) {
  const part = event.properties?.part ?? {}
  const tokens = part.tokens ?? {}
  const input = tokens.input ?? tokens.prompt ?? tokens.inputTokens ?? null
  const output = tokens.output ?? tokens.completion ?? tokens.outputTokens ?? null
  const total = tokens.total ?? tokens.totalTokens ?? null
  const cost = part.cost ?? part.costUSD ?? part.cost_usd ?? null
  return { input, output, total, cost }
}

function startServer() {
  if (server) return

  server = http.createServer((req, res) => {
    res.setHeader("Access-Control-Allow-Origin", "*")
    res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS")
    res.setHeader("Access-Control-Allow-Headers", "Content-Type")

    if (req.method === "OPTIONS") {
      res.writeHead(204)
      res.end()
      return
    }

    if (req.url === "/health") {
      res.writeHead(200, { "Content-Type": "text/plain" })
      res.end("ok")
      return
    }

    if (req.url === "/status/all") {
      const payload = getAllPayloads()
      res.writeHead(200, { "Content-Type": "application/json" })
      res.end(JSON.stringify(payload, null, 2))
      return
    }

    if (req.url === "/status" || req.url?.startsWith("/status?")) {
      // Check if ?all=1 or ?aggregate=1
      const isAll = req.url.includes("all=1") || req.url.includes("aggregate=1")
      if (isAll) {
        const payload = getAllPayloads()
        res.writeHead(200, { "Content-Type": "application/json" })
        res.end(JSON.stringify(payload, null, 2))
        return
      }

      // Default: latest active session
      const payload = getLatestActivePayload()
      if (payload) {
        res.writeHead(200, { "Content-Type": "application/json" })
        res.end(JSON.stringify(payload, null, 2))
      } else {
        res.writeHead(200, { "Content-Type": "application/json" })
        res.end(JSON.stringify({
          status: "idle",
          message: "no sessions",
          last_heartbeat: nowIso(),
          pending: 0,
          metadata: {},
        }, null, 2))
      }
      return
    }

    res.writeHead(404, { "Content-Type": "text/plain" })
    res.end("not found")
  })

  server.listen(PORT, HOST, () => {
    log("info", "tamagotchai status server listening", { port: PORT, host: HOST })
  })

  server.on("error", (err) => {
    log("error", "tamagotchai status server error", { error: err.message })
  })
}

function shutdownServer() {
  if (server) {
    server.close(() => log("info", "tamagotchai status server closed"))
    server = null
  }
}

function resolveSessionID(event) {
  return event.sessionID ?? event.properties?.info?.sessionID ?? "unknown"
}

export default async function TamagotchaiPlugin({ client, directory, project }) {
  logFn = client?.app?.log?.bind?.(client.app)
  projectName = project?.name ?? project?.id ?? directory?.split("/")?.pop?.() ?? "unknown"

  try {
    log("info", "starting tamagotchai plugin", { port: PORT, host: HOST, project: projectName })
    startServer()
  } catch (err) {
    log("error", "failed to start server", { error: err.message })
  }

  process.on("SIGTERM", () => { shutdownServer(); process.exit(0) })
  process.on("SIGINT", () => { shutdownServer(); process.exit(0) })
  process.on("beforeExit", shutdownServer)

  return {
    config: async (cfg) => {
      if (cfg.logLevel) log("info", `log level observed: ${cfg.logLevel}`)
    },

    "chat.message": async (input) => {
      const sid = resolveSessionID(input)
      setWorking(sid, `chat: ${input.agent ?? "unknown"}`)
    },

    event: async ({ event }) => {
      try {
        const sid = resolveSessionID(event)
        const s = getOrCreateSession(sid)

        switch (event.type) {
          case "session.created": {
            s.start_time = Date.now()
            s.message_count = 0
            s.files_modified.clear()
            s.metadata = {}
            s.metadata.project = projectName
            setWorking(sid, "session started")
            break
          }

          case "session.idle": {
            const duration = computeSessionDuration(sid)
            if (duration !== undefined) s.metadata.session_duration_ms = duration
            setIdle(sid)
            break
          }

          case "session.error": {
            const msg = event.error?.message ?? event.error ?? "session error"
            setError(sid, String(msg))
            break
          }

          case "session.status": {
            const st = event.status?.toLowerCase?.() ?? ""
            if (st === "waiting_input") {
              setSessionStatus(sid, "waiting_input", "waiting for input")
            } else if (st === "stuck") {
              setSessionStatus(sid, "stuck", "stuck")
            }
            break
          }

          case "command.executed": {
            const cmd = event.command ?? "unknown"
            s.metadata.tool_name = cmd
            setWorking(sid, `cmd: ${cmd}`)
            break
          }

          case "session.diff": {
            const diff = event.diff ?? {}
            if (typeof diff.additions === "number") {
              s.metadata.lines_added = (s.metadata.lines_added ?? 0) + diff.additions
            }
            if (typeof diff.deletions === "number") {
              s.metadata.lines_removed = (s.metadata.lines_removed ?? 0) + diff.deletions
            }
            if (typeof diff.commits === "number") {
              s.metadata.commits = (s.metadata.commits ?? 0) + diff.commits
            }
            setWorking(sid, "applying changes")
            break
          }

          case "message.updated": {
            const info = event.properties?.info
            if (info?.modelID && info?.providerID) {
              s.metadata.model = `${info.providerID}/${info.modelID}`
            } else if (info?.modelID) {
              s.metadata.model = info.modelID
            }
            s.message_count += 1
            updateSessionHeartbeat(sid)
            break
          }

          case "message.part.updated": {
            const part = event.properties?.part ?? {}
            if (part.type === "step-finish" || part.tokens || part.cost !== undefined) {
              const { input, output, total, cost } = extractPartTokens(event)
              if (input !== null) s.metadata.tokens_input = (s.metadata.tokens_input ?? 0) + input
              if (output !== null) s.metadata.tokens_output = (s.metadata.tokens_output ?? 0) + output
              if (total !== null) s.metadata.tokens_total = (s.metadata.tokens_total ?? 0) + total
              if (cost !== null) s.metadata.cost_usd = (s.metadata.cost_usd ?? 0) + cost
            }
            updateSessionHeartbeat(sid)
            break
          }

          case "tool_result": {
            const tool = event.tool ?? event.name ?? s.metadata.tool_name ?? "tool"
            const success = event.success ?? event.error === undefined
            s.metadata.tool_name = tool
            if (success) setSuccess(sid, `tool: ${tool}`)
            else setError(sid, `tool failed: ${tool}`)
            break
          }

          case "permission.asked": {
            setSessionStatus(sid, "waiting_input", `needs permission: ${event.permission ?? event.tool ?? "action"}`)
            s.pending = 1
            updateSessionHeartbeat(sid)
            break
          }

          case "permission.replied": {
            s.pending = 0
            setWorking(sid, "permission granted")
            break
          }

          case "file.edited": {
            const path = event.path ?? event.filePath ?? event.file ?? ""
            if (path) s.files_modified.add(path)
            updateSessionHeartbeat(sid)
            break
          }

          case "file.watcher.updated": {
            const path = event.path ?? event.filePath ?? event.file ?? ""
            if (path) s.files_modified.add(path)
            updateSessionHeartbeat(sid)
            break
          }

          default:
            updateSessionHeartbeat(sid)
        }
      } catch (err) {
        log("error", "event handler error", {
          eventType: event?.type,
          error: err instanceof Error ? err.message : String(err),
        })
      }
    },
  }
}
