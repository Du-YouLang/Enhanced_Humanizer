"""Finish GRANGER source review without rerunning completed numerical checks."""
import copy
import hashlib

from p6_gc_source_policy import checked_source_review


def finalize_gc_review(acceptance, text, review, *, original_sha256):
    checked_source_review(text,review)
    if (acceptance.get('verdict') != 'INDETERMINATE' or
            acceptance.get('numeric_verdict') != 'PASS_NUMERIC_REVIEW_PENDING' or
            acceptance.get('detail',{}).get('verdict') != 'PASS_NUMERIC_REVIEW_PENDING'):
        raise ValueError('Only completed independent numeric checks can finish source review')
    if not isinstance(original_sha256,str) or len(original_sha256)!=64:
        raise ValueError('Original numeric receipt hash required')
    result=copy.deepcopy(acceptance)
    result.update(verdict='PASS',reason='Independent numeric checks and exact substantive GPU source review passed',
                  source_review_evidence=review,numeric_receipt_sha256=original_sha256,
                  numerical_execution_reused=True,model_calls=0)
    result['detail'].update(source_review='INDEPENDENT_SOURCE_REVIEW_PASSED',source_review_evidence=review)
    return result
