/**
 * Minimal local telemetry for Pi. No prompts, responses, paths, or tool arguments.
 * Output is JSONL at .pi/metrics/usage.jsonl, which should be git-ignored.
 * Informational cost values are provider estimates, NOT a spending limit.
 */
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { mkdirSync, appendFileSync } from "node:fs";
import { join } from "node:path";

export default function (pi: ExtensionAPI) {
  let sessionModel = "unknown";
  let toolCalls = 0;
  let toolFailures = 0;
  let turnStart = 0;
  const write = (cwd: string, record: Record<string, unknown>) => {
    const dir = join(cwd, ".pi", "metrics");
    mkdirSync(dir, { recursive: true });
    appendFileSync(join(dir, "usage.jsonl"), JSON.stringify({ timestamp: new Date().toISOString(), ...record }) + "\n");
  };

  pi.on("session_start", async (_event, ctx) => {
    sessionModel = ctx.model ? `${ctx.model.provider}/${ctx.model.id}` : "unknown";
  });
  pi.on("model_select", async (event) => {
    sessionModel = `${event.model.provider}/${event.model.id}`;
  });
  pi.on("agent_start", async () => { toolCalls = 0; toolFailures = 0; turnStart = Date.now(); });
  pi.on("tool_execution_end", async (event) => { toolCalls++; if (event.isError) toolFailures++; });
  pi.on("message_end", async (event, ctx) => {
    if (event.message.role !== "assistant") return;
    const usage = event.message.usage;
    write(ctx.cwd, {
      event: "assistant_usage", model: sessionModel,
      inputTokens: usage?.input ?? null,
      outputTokens: usage?.output ?? null,
      cacheReadTokens: usage?.cacheRead ?? null,
      cacheWriteTokens: usage?.cacheWrite ?? null,
      estimatedCostUSD: usage?.cost?.total ?? null
    });
  });
  pi.on("agent_end", async (_event, ctx) => {
    write(ctx.cwd, { event: "run_end", model: sessionModel,
      toolCalls, toolFailures, elapsedMs: Date.now() - turnStart });
  });
}
