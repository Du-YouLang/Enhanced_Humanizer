"""One explicit source repair; callers must create a separate diagnostic copy."""
import hashlib


def repaired_text(original,expected_sha256):
    if hashlib.sha256(original.encode()).hexdigest()!=expected_sha256:
        raise ValueError('Exact original source binding required')
    before='        if (tid < d) sG[tid * d + tid] += ridge;\n        if (tid < p * p) {'
    after='        if (tid < d) sG[tid * d + tid] += ridge;\n        __syncthreads(); // Publish ridge writes before cross-warp restricted copy.\n        if (tid < p * p) {'
    if original.count(before)!=1:raise ValueError('One exact missing-barrier site required')
    return original.replace(before,after,1)
