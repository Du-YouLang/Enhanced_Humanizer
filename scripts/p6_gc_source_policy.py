"""Conservative transfer screening with explicit Python dictionary exceptions."""
import ast
import hashlib

REVIEW_CHECKS = {'substantive_gpu_regression','no_signal_or_regression_download',
                 'no_dummy_kernel_or_gold_lookup','frozen_target_ridge_rss_formula',
                 'metadata_only_host_processing','no_guard_monkeypatch'}


def checked_source_review(text, review):
    """Bind an independent private source review to its exact text and lines."""
    if (not isinstance(review, dict) or review.get('reviewer') != 'independent_acceptance' or
            review.get('source_sha256') != hashlib.sha256(text.encode()).hexdigest() or
            set(review.get('checks', {})) != REVIEW_CHECKS or
            any(value is not True for value in review['checks'].values()) or
            not isinstance(review.get('finding'), str) or not review['finding'].strip()):
        raise ValueError('Exact complete independent GC source review required')
    lines=review.get('metadata_download_lines', [])
    if (not isinstance(lines, list) or any(type(line) is not int or line <= 0 for line in lines) or
            len(lines) != len(set(lines))):
        raise ValueError('Invalid reviewed metadata download locations')
    tree=ast.parse(text)
    actual={node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call) and
            isinstance(node.func, ast.Attribute) and node.func.attr == 'asnumpy'}
    if set(lines) != actual:
        raise ValueError('Every metadata download must have an exact source review')
    validate_gc_source(text, metadata_download_lines=lines)
    return review


def validate_gc_source(text, *, metadata_download_lines=()):
    tree = ast.parse(text)
    stores = {}
    assignments = {}
    definitions = {}
    star_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):assignments[id(target)] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assignments[id(node.target)] = node.value
    # Count every binding, including comprehensions, with/except, pattern
    # captures and nested definitions. An ambiguous name stays refused.
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            stores.setdefault(node.id, []).append(assignments.get(id(node)))
        elif isinstance(node, ast.arg):stores.setdefault(node.arg, []).append(None)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.setdefault(node.name, []).append(node)
            stores.setdefault(node.name, []).append(None)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            stores.setdefault(node.name, []).append(None)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            stores.setdefault(node.name, []).append(None)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            stores.setdefault(node.rest, []).append(None)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for name in node.names:
                star_import |= name.name == '*'
                stores.setdefault(name.asname or name.name.split('.')[0], []).append(None)
    functions = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and not n.decorator_list and len(stores[n.name]) == 1 and len(definitions[n.name]) == 1}

    def dictionary(value):
        return (isinstance(value, ast.Dict) or
                isinstance(value, ast.Attribute) and value.attr == '__dict__' and
                isinstance(value.value, ast.Name) and value.value.id in functions)

    def safe_get(receiver):
        if star_import:return isinstance(receiver, ast.Dict)
        if dictionary(receiver):return True
        if not isinstance(receiver, ast.Name):return False
        values = stores.get(receiver.id, [])
        return len(values) == 1 and dictionary(values[0])

    for node in ast.walk(tree):
        modules = []
        if isinstance(node, ast.Import):modules = [n.name.split('.')[0] for n in node.names]
        elif isinstance(node, ast.ImportFrom):modules = [(node.module or '').split('.')[0]]
        if {'torch', 'scipy', 'subprocess', 'ctypes'} & set(modules):
            raise ValueError('Forbidden regression dependency')
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            name = node.func.attr
            if (name == 'tofile' or name == 'asnumpy' and node.lineno not in metadata_download_lines or
                    name == 'get' and not safe_get(node.func.value)):
                raise ValueError('Device-to-host regression route requires source review; refused')
    return tree
