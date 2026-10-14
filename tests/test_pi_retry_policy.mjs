import test from 'node:test';
import assert from 'node:assert/strict';
import {transientProviderError,recoveryGuard} from '../benchmarks/pi-comparison/runners/pi_retry_policy.mjs';

test('overload retries; quota, auth, and context errors do not',()=>{
  for(const errorMessage of ['Our servers are currently overloaded. Please try again later.','503 server unavailable','ECONNRESET'])
    assert.equal(transientProviderError({stopReason:'error',errorMessage}),true);
  for(const errorMessage of ['401 authentication overloaded','429 insufficient_quota','context_length_exceeded','invalid_request_error'])
    assert.equal(transientProviderError({stopReason:'error',errorMessage}),false);
});
test('fifth consecutive error stops and successful work resets the burst',()=>{
  const g=recoveryGuard(1),error={stopReason:'error',errorMessage:'server_is_overloaded'};
  for(let count=2;count<=5;count++)assert.deepEqual(g.observe(error),{
    retry:count<5,consecutive_failures:count,state:count<5?'SHOULD_RETRY':'NETWORK_CHECK_REQUIRED'});
  assert.equal(g.observe({stopReason:'toolUse'}).consecutive_failures,0);
  assert.equal(g.observe(error).consecutive_failures,1);
});
