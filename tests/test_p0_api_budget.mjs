import test from 'node:test';
import assert from 'node:assert/strict';
import { reserveTextRequest } from '../scripts/p0_api_budget.mjs';

const approval = { status: 'AUTHORIZED_P0_ONLY', inference_enabled: true,
  authorized_p0_limits: { deepseek_inference_requests: 4, api_cash_usd: 1 } };
const empty = () => ({ deepseek_requests_reserved: 0, reserved_peak_cash_usd: 0, probes: [] });

test('no approval, invalid limits, or corrupt ledger fail closed', () => {
  assert.throws(() => reserveTextRequest(empty(), { ...approval, inference_enabled: false }, 'test'));
  for (const invalid of [NaN, -1, '0', Infinity]) {
    assert.throws(() => reserveTextRequest({ ...empty(), reserved_peak_cash_usd: invalid }, approval, 'test'));
  }
});

test('conservative cash cap can stop before the request count cap', () => {
  let ledger = empty();
  for (let i = 0; i < 3; i++) ledger = reserveTextRequest(ledger, approval, 'test');
  assert.equal(ledger.deepseek_requests_reserved, 3);
  assert.throws(() => reserveTextRequest(ledger, approval, 'fourth'));
  assert.equal(ledger.deepseek_requests_reserved, 3);
  assert.ok(ledger.reserved_peak_cash_usd < 1);
});

test('request cap rejects without mutating the persistent reservation', () => {
  const before = { ...empty(), deepseek_requests_reserved: 4 };
  assert.throws(() => reserveTextRequest(before, approval, 'test'));
  assert.deepEqual(before, { ...empty(), deepseek_requests_reserved: 4 });
});
