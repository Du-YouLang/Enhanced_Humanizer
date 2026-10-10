/** Reservation policy for the P0 text probe, not a general Coding Agent budget. */
export function reserveTextRequest(ledger, approval, observedAt, logprobs = false) {
  if (approval.status !== 'AUTHORIZED_P0_ONLY' || approval.inference_enabled !== true) {
    throw new Error('P0 inference is not authorized');
  }
  const limits = approval.authorized_p0_limits;
  const fields = [ledger.deepseek_requests_reserved, ledger.reserved_peak_cash_usd,
    limits?.deepseek_inference_requests, limits?.api_cash_usd];
  if (!fields.every(x => typeof x === 'number' && Number.isFinite(x) && x >= 0)
      || !Number.isInteger(ledger.deepseek_requests_reserved)
      || !Number.isInteger(limits.deepseek_inference_requests)
      || !Array.isArray(ledger.probes)) throw new Error('Invalid budget ledger or limits');
  const reserve = (1048576 * 0.3 + 64 * 1.2) / 1000000;
  if (ledger.deepseek_requests_reserved >= limits.deepseek_inference_requests
      || ledger.reserved_peak_cash_usd + reserve > limits.api_cash_usd) {
    throw new Error('P0 request or cash reservation exhausted');
  }
  return {
    ...ledger,
    deepseek_requests_reserved: ledger.deepseek_requests_reserved + 1,
    reserved_peak_cash_usd: ledger.reserved_peak_cash_usd + reserve,
    probes: [...ledger.probes, { observed_at: observedAt, logprobs, reserved_peak_cash_usd: reserve }],
  };
}
