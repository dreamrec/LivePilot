#!/usr/bin/env node
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import readline from "node:readline";

const DEFAULT_CODEX = "/Users/terencemahon/.npm-global/bin/codex";
const CLIENT_INFO = {
  name: "livepilot_codex_gate",
  title: "LivePilot Codex Gate Harness",
  version: "0.1.0",
};

function usage() {
  return `Usage:
  node scripts/codex_gate/harness.mjs [--home PATH] start-thread [--model MODEL] [--cwd PATH] [--prompt TEXT]
  node scripts/codex_gate/harness.mjs [--home PATH] send-turn --thread THREAD_ID --prompt TEXT [--cwd PATH]
  node scripts/codex_gate/harness.mjs [--home PATH] read-thread --thread THREAD_ID
  node scripts/codex_gate/harness.mjs [--home PATH] resume-thread --thread THREAD_ID

Options:
  --home PATH        CODEX_HOME/CODEX_SQLITE_HOME for the app-server child.
  --codex PATH       Codex CLI path. Default: ${DEFAULT_CODEX}
  --timeout-ms N     Request/turn timeout. Default: 120000
  --model MODEL      Optional model override for thread/start.
  --cwd PATH         Optional workspace path for thread/start or turn/start.
  --thread ID        Thread id for send/read/resume.
  --prompt TEXT      Prompt text for send-turn, or optional first turn for start-thread.
`;
}

function parseArgs(argv) {
  const options = {
    codex: DEFAULT_CODEX,
    timeoutMs: 120000,
    home: "",
    model: "",
    cwd: "",
    thread: "",
    prompt: "",
  };
  const rest = [];
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith("--")) {
      rest.push(arg);
      continue;
    }
    const [rawKey, inlineValue] = arg.slice(2).split(/=(.*)/s, 2);
    const key = rawKey.replace(/-([a-z])/g, (_, ch) => ch.toUpperCase());
    const value = inlineValue !== undefined ? inlineValue : argv[++i];
    if (value === undefined) {
      throw new Error(`Missing value for --${rawKey}`);
    }
    if (key === "timeoutMs") {
      options.timeoutMs = Number(value);
    } else if (Object.hasOwn(options, key)) {
      options[key] = value;
    } else {
      throw new Error(`Unknown option: --${rawKey}`);
    }
  }
  const [command, ...positionals] = rest;
  if (!command) throw new Error(usage());
  if (!Number.isFinite(options.timeoutMs) || options.timeoutMs < 1000) {
    throw new Error("--timeout-ms must be at least 1000");
  }
  if (!options.prompt && positionals.length) {
    options.prompt = positionals.join(" ");
  }
  return { command, options };
}

class AppServerClient {
  constructor(options) {
    this.options = options;
    this.nextId = 1;
    this.pending = new Map();
    this.trace = [];
    this.notifications = [];
    this.stderr = "";
    this.proc = null;
    this.rl = null;
  }

  async start() {
    const env = { ...process.env };
    if (this.options.home) {
      const home = path.resolve(this.options.home);
      fs.mkdirSync(home, { recursive: true });
      env.CODEX_HOME = home;
      env.CODEX_SQLITE_HOME = home;
    }
    this.proc = spawn(
      this.options.codex,
      ["app-server", "--listen", "stdio://"],
      {
        cwd: process.cwd(),
        env,
        stdio: ["pipe", "pipe", "pipe"],
      },
    );
    this.proc.stderr.setEncoding("utf8");
    this.proc.stderr.on("data", chunk => {
      this.stderr += chunk;
    });
    this.rl = readline.createInterface({ input: this.proc.stdout });
    this.rl.on("line", line => this.#handleLine(line));
    this.proc.on("exit", (code, signal) => {
      for (const entry of this.pending.values()) {
        entry.reject(new Error(`app-server exited before response: code=${code} signal=${signal}`));
      }
      this.pending.clear();
    });

    const initialize = await this.request("initialize", {
      clientInfo: CLIENT_INFO,
      capabilities: {
        experimentalApi: true,
      },
    });
    this.notify("initialized", {});
    return initialize;
  }

  async stop() {
    if (!this.proc) return;
    this.rl?.close();
    if (this.proc.exitCode === null) {
      this.proc.stdin.end();
      this.proc.kill("SIGTERM");
      await new Promise(resolve => {
        const timer = setTimeout(resolve, 1000);
        this.proc.once("exit", () => {
          clearTimeout(timer);
          resolve();
        });
      });
    }
  }

  request(method, params = {}) {
    const id = this.nextId;
    this.nextId += 1;
    const message = { method, id, params };
    this.trace.push({ direction: "client", message });
    this.proc.stdin.write(`${JSON.stringify(message)}\n`);
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Timed out waiting for ${method}`));
      }, this.options.timeoutMs);
      this.pending.set(id, {
        method,
        resolve: msg => {
          clearTimeout(timer);
          if (msg.error) {
            const error = new Error(msg.error.message || `${method} failed`);
            error.payload = msg.error;
            reject(error);
          } else {
            resolve(msg.result);
          }
        },
        reject: error => {
          clearTimeout(timer);
          reject(error);
        },
      });
    });
  }

  notify(method, params = {}) {
    const message = { method, params };
    this.trace.push({ direction: "client", message });
    this.proc.stdin.write(`${JSON.stringify(message)}\n`);
  }

  async waitForTurnComplete(startedAt = this.notifications.length) {
    return new Promise((resolve, reject) => {
      let interval;
      const timer = setTimeout(() => {
        clearInterval(interval);
        reject(new Error("Timed out waiting for turn/completed"));
      }, this.options.timeoutMs);
      const check = () => {
        for (const notification of this.notifications.slice(startedAt)) {
          if (notification.method === "turn/completed") {
            clearTimeout(timer);
            resolve(notification);
            return true;
          }
        }
        return false;
      };
      if (check()) return;
      interval = setInterval(() => {
        if (check()) clearInterval(interval);
      }, 100);
    });
  }

  #handleLine(line) {
    let message;
    try {
      message = JSON.parse(line);
    } catch (_error) {
      this.trace.push({ direction: "server", malformed: line });
      return;
    }
    this.trace.push({ direction: "server", message });
    if (message.id !== undefined) {
      const entry = this.pending.get(message.id);
      if (entry) {
        this.pending.delete(message.id);
        entry.resolve(message);
      }
      return;
    }
    this.notifications.push(message);
  }
}

function extractAssistantText(notifications) {
  return notifications
    .filter(item => item.method === "item/agentMessage/delta")
    .map(item => item.params?.delta || item.params?.text || "")
    .join("");
}

async function runCommand(command, options) {
  const client = new AppServerClient(options);
  const output = {
    status: "ok",
    command,
    home: options.home ? path.resolve(options.home) : "",
    codex: options.codex,
  };
  try {
    output.initialize = await client.start();
    if (command === "start-thread") {
      const params = {};
      if (options.model) params.model = options.model;
      if (options.cwd) params.cwd = path.resolve(options.cwd);
      output.result = await client.request("thread/start", params);
      if (options.prompt) {
        const threadId = output.result?.thread?.id;
        if (!threadId) throw new Error("thread/start did not return a thread id");
        const notificationStart = client.notifications.length;
        output.first_turn = await client.request("turn/start", {
          threadId,
          input: [{ type: "text", text: options.prompt }],
          ...(options.cwd ? { cwd: path.resolve(options.cwd) } : {}),
        });
        output.turn_completed = await client.waitForTurnComplete(notificationStart);
        output.assistant_text = extractAssistantText(client.notifications);
      }
    } else if (command === "send-turn") {
      if (!options.thread) throw new Error("--thread is required");
      if (!options.prompt) throw new Error("--prompt is required");
      const resumeParams = { threadId: options.thread };
      if (options.model) resumeParams.model = options.model;
      if (options.cwd) resumeParams.cwd = path.resolve(options.cwd);
      output.resume = await client.request("thread/resume", resumeParams);
      const notificationStart = client.notifications.length;
      const params = {
        threadId: options.thread,
        input: [{ type: "text", text: options.prompt }],
      };
      if (options.cwd) params.cwd = path.resolve(options.cwd);
      if (options.model) params.model = options.model;
      output.result = await client.request("turn/start", params);
      output.turn_completed = await client.waitForTurnComplete(notificationStart);
      output.assistant_text = extractAssistantText(client.notifications);
    } else if (command === "read-thread") {
      if (!options.thread) throw new Error("--thread is required");
      output.result = await client.request("thread/read", {
        threadId: options.thread,
        includeTurns: true,
      });
    } else if (command === "resume-thread") {
      if (!options.thread) throw new Error("--thread is required");
      const params = {
        threadId: options.thread,
      };
      if (options.model) params.model = options.model;
      if (options.cwd) params.cwd = path.resolve(options.cwd);
      output.result = await client.request("thread/resume", params);
    } else {
      throw new Error(`Unknown command: ${command}\n${usage()}`);
    }
    return output;
  } catch (error) {
    output.status = "error";
    output.error = error.message;
    if (error.payload) output.error_payload = error.payload;
    return output;
  } finally {
    output.notifications = client.notifications;
    output.trace = client.trace;
    output.stderr = client.stderr;
    await client.stop();
  }
}

async function main() {
  try {
    const { command, options } = parseArgs(process.argv.slice(2));
    const output = await runCommand(command, options);
    console.log(JSON.stringify(output, null, 2));
    process.exitCode = output.status === "ok" ? 0 : 1;
  } catch (error) {
    console.error(error.message);
    process.exitCode = 2;
  }
}

main();
