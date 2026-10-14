"""Pure validation of the prespecified Pi comparison, never an executor."""
import hashlib
import json
import ast


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def validate_plan(value):
    body=dict(value);expected=body.pop('plan_sha256',None)
    cells=[{'task_id':tid,'profile':p,'provider':provider,'repetition':0}
           for tid in ('BIP-black-2','SCI-GRANGER-GPU') for provider in ('deepseek','subscription') for p in ('P0','P1','P2','P3')]
    if (digest(body)!=expected or body.get('cells')!=cells or body.get('bulk_256_enabled') is not False
            or body.get('external_release_authorized') is not False):
        raise ValueError('Exact prespecified sixteen cells and no release/bulk required')
    return value


def settled_usage_match(summary,rows):
    known=[r for r in rows if 'usage' in r]
    fields={'input_tokens':'input_tokens','output_tokens':'output_tokens',
            'cache_read_tokens':'cache_read_input_tokens','cache_write_tokens':'cache_creation_input_tokens'}
    return bool(known) and all(summary.get('usage',{}).get(k)==sum(r['usage'][v] for r in known) for k,v in fields.items())


def validate_deepseek_roles(body):
    roles=[m.get('role') for m in body.get('messages',[])]
    if not roles or any(r not in ('system','user','assistant','tool') for r in roles):
        raise ValueError('DeepSeek requires the pinned system/user/assistant/tool message schema')
    return roles


def zero_numeric_returns(text,function):
    """An actual wrong-number negative control; refuse a misspelled target."""
    changed=[]
    class Mutate(ast.NodeTransformer):
        def visit_FunctionDef(self,node):
            if node.name!=function:return node
            class Zero(ast.NodeTransformer):
                def visit_Return(self,n):
                    if n.value:
                        n.value=ast.BinOp(left=n.value,op=ast.Mult(),right=ast.Constant(value=0.0))
                        changed.append(n.lineno)
                    return n
            return Zero().visit(node)
    value=ast.unparse(ast.fix_missing_locations(Mutate().visit(ast.parse(text))))
    if not changed:raise ValueError('Negative-control target did not change')
    return value
