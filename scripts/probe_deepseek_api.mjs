/** P0 only: one bounded HTTPS text request; no tools, redirects, or retries. */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { reserveTextRequest } from './p0_api_budget.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const approval = JSON.parse(fs.readFileSync(path.join(root, 'configs/budget-proposal.json'), 'utf8'));
if (approval.status !== 'AUTHORIZED_P0_ONLY' || !approval.inference_enabled) {
  throw new Error('P0 model budget is not authorized');
}
if (process.argv.slice(2).some(x => x !== '--logprobs')) throw new Error('Unsupported argument');
if (process.env.DEEPSEEK_BASE_URL) throw new Error('Custom endpoint is outside this probe');
const logprobs = process.argv.includes('--logprobs');
const limits = approval.authorized_p0_limits;
const auditDir = path.join(root, '.local-workbench/audits');
fs.mkdirSync(auditDir, { recursive: true });
const ledgerPath = path.join(auditDir, 'p0-model-budget.json');
const lockPath = ledgerPath + '.lock';
const lock = fs.openSync(lockPath, 'wx'); // Fail closed if another probe owns the budget.
const requestStarted = new Date().toISOString();
const tick = performance.now();
const record = {
  kind: 'DIRECT_API_TEXT_ONLY', observed_at: requestStarted,
  endpoint: 'https://api.deepseek.com/chat/completions', requested_model: 'deepseek-flash',
  requested_logprobs: logprobs, max_tokens: 64, thinking: 'disabled',
  tool_access: false, redirects: false, automatic_retries: 0,
  price_source: 'https://api-docs.deepseek.com/quick_start/pricing/',
  price_snapshot_date: '2026-10-10',
  peak_usd_per_million: { input_miss: 0.3, input_hit: 0.006, output: 1.2 },
  cash_bill_usd: 'unavailable', credential_source: 'unavailable',
};
try {
  let key = process.env.DEEPSEEK_API_KEY;
  if (key) record.credential_source = 'existing_process_environment';
  else {
    const npmRoot = execFileSync('cmd.exe', ['/d', '/c', 'npm root -g'], { encoding: 'utf8', timeout: 10000 }).trim();
    const require = createRequire(import.meta.url);
    const yaml = require(path.join(npmRoot, '@deepseek-ai/dsh/node_modules/js-yaml'));
    const home = process.env.DSH_HOME || path.join(process.env.USERPROFILE, '.dsh');
    const credentials = yaml.load(fs.readFileSync(path.join(home, '.credentials.yaml'), 'utf8'));
    key = credentials?.refs?.DEEPSEEK_API_KEY;
    record.credential_source = 'existing_dsh_saved_ref';
  }
  if (typeof key !== 'string' || !key.length) throw new Error('Credential unavailable');
  const before = fs.existsSync(ledgerPath)
    ? JSON.parse(fs.readFileSync(ledgerPath, 'utf8'))
    : { schema_version: 1, deepseek_requests_reserved: 0, reserved_peak_cash_usd: 0, codex_turns_used: 0, probes: [] };
  // Reserve the entire documented 1M context at peak input price, plus the capped output.
  // This deliberately over-reserves; a failed/aborted call retains its reservation.
  const ledger = reserveTextRequest(before, approval, requestStarted, logprobs);
  fs.writeFileSync(ledgerPath, JSON.stringify(ledger, null, 2) + '\n'); // Before network.
  record.request_index = ledger.deepseek_requests_reserved;
  record.reserved_peak_cash_usd = ledger.probes.at(-1).reserved_peak_cash_usd;
  const payload = {
    model: record.requested_model,
    messages: [{ role: 'user', content: 'Reply with exactly P0_API_OK.' }],
    max_tokens: record.max_tokens, stream: false, thinking: { type: 'disabled' },
    ...(logprobs ? { logprobs: true, top_logprobs: 2 } : {}),
  };
  const response = await fetch(record.endpoint, {
    method: 'POST', redirect: 'error',
    signal: AbortSignal.timeout(Math.max(1, Math.floor(Math.min(limits.per_probe_timeout_seconds, 120) * 1000 - (performance.now() - tick)))),
    headers: { Authorization: 'Bearer ' + key, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  key = undefined;
  record.http_status = response.status;
  const data = await response.json();
  for (const field of ['code', 'type', 'param']) {
    const value = data.error?.[field];
    if (typeof value === 'string' && /^[a-zA-Z0-9_.-]{1,80}$/.test(value)) record['api_error_' + field] = value;
  }
  const first = data.choices?.[0];
  record.request_id = data.id || response.headers.get('x-request-id') || 'unavailable';
  record.returned_model = data.model || 'unavailable';
  record.finish_reason = first?.finish_reason || 'unavailable';
  record.expected_text_match = first?.message?.content?.trim() === 'P0_API_OK';
  record.usage = data.usage || 'unavailable';
  record.logprobs_returned = Array.isArray(first?.logprobs?.content) && first.logprobs.content.length > 0;
  record.logprob_token_count = first?.logprobs?.content?.length || 0;
  record.verdict = !response.ok ? 'API_REJECTED' : logprobs && !record.logprobs_returned
    ? 'LOGPROBS_UNAVAILABLE' : record.expected_text_match ? 'PASS' : 'UNEXPECTED_RESPONSE';
  if (data.usage?.prompt_tokens !== undefined && data.usage?.completion_tokens !== undefined) {
    const u = data.usage;
    const hit = u.prompt_cache_hit_tokens || 0;
    const miss = u.prompt_cache_miss_tokens ?? Math.max(0, u.prompt_tokens - hit);
    record.estimated_peak_cost_usd = (miss * 0.3 + hit * 0.006 + u.completion_tokens * 1.2) / 1000000;
    record.estimated_off_peak_cost_usd = record.estimated_peak_cost_usd / 2;
  }
} catch (error) {
  record.verdict = 'INFRA_FAIL';
  record.error_type = error.name; // Never persist raw messages, headers, or credentials.
} finally {
  record.elapsed_seconds = (performance.now() - tick) / 1000;
  const dest = path.join(auditDir, `deepseek-text-${Date.now()}${logprobs ? '-logprobs' : ''}.json`);
  fs.writeFileSync(dest, JSON.stringify(record, null, 2) + '\n');
  fs.closeSync(lock);
  fs.unlinkSync(lockPath);
  console.log(JSON.stringify({ ...record, evidence: dest }, null, 2));
}
process.exitCode = record.verdict === 'PASS' ? 0 : 1;
