// Transport policy only. The installed official Pi SDK owns retry and tools.
export function transientProviderError(message) {
  if(message?.stopReason!=='error')return false;
  const text=String(message.errorMessage??'');
  if(/insufficient_quota|usage_limit|spend_limit|billing|credit balance|authentication|invalid.api.key|\b401\b|\b403\b|invalid_request|unsupported|context_length|maximum context/i.test(text))return false;
  return /server_is_overloaded|server_overloaded|overloaded|temporarily unavailable|service_unavailable|\b50[0234]\b|econnreset|socket hang up|connection reset|connection error|fetch failed|network error|timed out|timeout|\b429\b|rate.limit/i.test(text);
}

export function recoveryGuard(priorFailures=0) {
  if(!Number.isInteger(priorFailures)||priorFailures<0||priorFailures>=5)throw new Error('Invalid prior failure count');
  let failures=priorFailures;
  return {
    observe(message) {
      if(message?.stopReason==='error') {
        const transient=transientProviderError(message);
        if(transient)failures++;
        return {retry:transient&&failures<5,consecutive_failures:failures,
          state:transient?(failures>=5?'NETWORK_CHECK_REQUIRED':'SHOULD_RETRY'):'NON_RETRYABLE'};
      }
      if(message?.stopReason!=='aborted')failures=0;
      return {retry:message?.stopReason!=='aborted',consecutive_failures:failures,state:message?.stopReason==='aborted'?'ROLE_STOPPED':'COMPLETED'};
    },
    failures:()=>failures,
  };
}
