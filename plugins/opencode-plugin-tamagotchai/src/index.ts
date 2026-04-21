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

// ---- state ----
const state = {
  status: "idle",
  message: "",
  last_heartbeat: nowIso(),
  pending: 0,
  metadata: {},
}
const sessionStarts = new Map()
let messageCount = 0
let filesModified = new Set()
let projectName = ""

function updateHeartbeat() {
  state.last_heartbeat = nowIso()
}

function setWorking(msg) {
  state.status = "working"
  state.pending = Math.max(1, state.pending)
  if (msg) state.message = msg
  updateHeartbeat()
}

function setIdle() {
  state.status = "idle"
  state.pending = 0
  state.message = ""
  updateHeartbeat()
}

function setError(msg) {
  state.status = "error"
  state.pending = 0
  if (msg) state.message = msg
  updateHeartbeat()
}

function setSuccess(msg) {
  state.status = "success"
  state.pending = 0
  if (msg) state.message = msg
  updateHeartbeat()
}

function computeSessionDuration(sessionID) {
  const start = sessionStarts.get(sessionID)
  if (!start) return undefined
  return Date.now() - start
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

function buildMetadata() {
  const meta = { ...state.metadata }
  if (projectName) meta.project = projectName
  if (messageCount > 0) meta.message_count = messageCount
  if (filesModified.size > 0) meta.files_modified = filesModified.size
  return stripNulls(meta)
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

    if (req.url === "/status" || req.url?.startsWith("/status")) {
      for (const [sid, start] of sessionStarts.entries()) {
        if (state.status !== "idle") {
          state.metadata.session_duration_ms = Date.now() - start
        }
      }
      const payload = {
        status: state.status,
        message: state.message,
        last_heartbeat: state.last_heartbeat,
        pending: state.pending,
        metadata: buildMetadata(),
      }
      res.writeHead(200, { "Content-Type": "application/json" })
      res.end(JSON.stringify(payload, null, 2))
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

export default async function TamagotchaiPlugin({ client, directory, project }) {
  logFn = client?.app?.log?.bind?.(client.app)
  projectName = project?.name ?? project?.id ?? directory?.split("/")?.pop?.() ?? "unknown"
  state.metadata.project = projectName

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
      setWorking(`chat: ${input.agent ?? "unknown"}`)
    },

    event: async ({ event }) => {
      try {
        switch (event.type) {
          case "session.created": {
            const sid = event.sessionID ?? event.properties?.info?.sessionID ?? "unknown"
            sessionStarts.set(sid, Date.now())
            messageCount = 0
            filesModified.clear()
            state.metadata = {}
            state.metadata.project = projectName
            setWorking("session started")
            break
          }

          case "session.idle": {
            const sid = event.sessionID ?? event.properties?.info?.sessionID ?? "unknown"
            const duration = computeSessionDuration(sid)
            if (duration !== undefined) state.metadata.session_duration_ms = duration
            setIdle()
            break
          }

          case "session.error": {
            const msg = event.error?.message ?? event.error ?? "session error"
            setError(String(msg))
            break
          }

          case "session.status": {
            const st = event.status?.toLowerCase?.() ?? ""
            if (st === "waiting_input") {
              state.status = "waiting_input"
              state.message = "waiting for input"
              updateHeartbeat()
            } else if (st === "stuck") {
              state.status = "stuck"
              state.message = "stuck"
              updateHeartbeat()
            }
            break
          }

          case "command.executed": {
            const cmd = event.command ?? "unknown"
            state.metadata.tool_name = cmd
            setWorking(`cmd: ${cmd}`)
            break
          }

          case "session.diff": {
            const diff = event.diff ?? {}
            if (typeof diff.additions === "number") {
              state.metadata.lines_added = (state.metadata.lines_added ?? 0) + diff.additions
            }
            if (typeof diff.deletions === "number") {
              state.metadata.lines_removed = (state.metadata.lines_removed ?? 0) + diff.deletions
            }
            if (typeof diff.commits === "number") {
              state.metadata.commits = (state.metadata.commits ?? 0) + diff.commits
            }
            setWorking("applying changes")
            break
          }

          case "message.updated": {
            const info = event.properties?.info
            if (info?.modelID && info?.providerID) {
              state.metadata.model = `${info.providerID}/${info.modelID}`
            } else if (info?.modelID) {
              state.metadata.model = info.modelID
            }
            messageCount += 1
            updateHeartbeat()
            break
          }

          case "message.part.updated": {
            const part = event.properties?.part ?? {}

            // Token/cost extraction (step-finish parts)
            if (part.type === "step-finish" || part.tokens || part.cost !== undefined) {
              const { input, output, total, cost } = extractPartTokens(event)
              if (input !== null) state.metadata.tokens_input = (state.metadata.tokens_input ?? 0) + input
              if (output !== null) state.metadata.tokens_output = (state.metadata.tokens_output ?? 0) + output
              if (total !== null) state.metadata.tokens_total = (state.metadata.tokens_total ?? 0) + total
              if (cost !== null) state.metadata.cost_usd = (state.metadata.cost_usd ?? 0) + cost
            }

            updateHeartbeat()
            break
          }

          case "tool_result": {
            const tool = event.tool ?? event.name ?? state.metadata.tool_name ?? "tool"
            const success = event.success ?? event.error === undefined
            state.metadata.tool_name = tool
            if (success) setSuccess(`tool: ${tool}`)
            else setError(`tool failed: ${tool}`)
            break
          }

          case "permission.asked": {
            state.status = "waiting_input"
            state.message = `needs permission: ${event.permission ?? event.tool ?? "action"}`
            state.pending = 1
            updateHeartbeat()
            break
          }

          case "permission.replied": {
            state.pending = 0
            setWorking("permission granted")
            break
          }

          case "file.edited": {
            const path = event.path ?? event.filePath ?? event.file ?? ""
            if (path) filesModified.add(path)
            updateHeartbeat()
            break
          }

          case "file.watcher.updated": {
            const path = event.path ?? event.filePath ?? event.file ?? ""
            if (path) filesModified.add(path)
            updateHeartbeat()
            break
          }

          default:
            updateHeartbeat()
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
