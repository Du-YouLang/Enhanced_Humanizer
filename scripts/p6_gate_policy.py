"""Public, explicit file rules shared by prompts and independent acceptance."""
from pathlib import Path, PurePosixPath


GENERATION_RULES = (
    'Existing test and fixture files are immutable, including test_*.py, '
    '*_test.py, conftest.py and files anywhere under tests/ or testing/. '
    'Do not append tests to an existing file, even if its original tests are preserved. '
    'Add regression tests only in a NEW file; existing dependency configuration is also immutable. '
    'A passing test run does not override these file rules. '
    'Commit the implementation and any new test files, leaving a clean worktree.'
)


def protected_changes(changed, baseline, explicit=()):
    """New regression files are allowed; original test bytes are protected."""
    baseline = Path(baseline)
    explicit = set(explicit)
    result = []
    for name in changed:
        path = PurePosixPath(name)
        test = (any(part in ('tests', 'testing') for part in path.parts) or
                path.name.startswith('test_') or path.name.endswith('_test.py') or
                path.name == 'conftest.py')
        dependency = path.name in ('pyproject.toml', 'setup.py', 'requirements.txt', 'setup.cfg')
        if name in explicit or ((test or dependency) and (baseline/name).exists()):
            result.append(name)
    return result
