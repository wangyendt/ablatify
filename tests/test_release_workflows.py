"""Keep automatic and manually dispatched releases behind the same CI matrix."""
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / '.github' / 'workflows'


def workflow(name):
    # BaseLoader preserves YAML's `on` key instead of treating it as a boolean.
    return yaml.load((WORKFLOWS / name).read_text(encoding='utf-8'), Loader=yaml.BaseLoader)


def test_reusable_ci_verifies_all_platforms_at_the_requested_sha():
    ci = workflow('ci.yml')
    assert ci['on']['workflow_call']['inputs']['ref']['required'] == 'true'
    verify = ci['jobs']['verify']
    assert verify['strategy']['fail-fast'] == 'false'
    assert set(verify['strategy']['matrix']['os']) == {
        'ubuntu-latest', 'macos-latest', 'windows-latest',
    }
    assert set(verify['strategy']['matrix']['python']) == {'3.9', '3.14'}
    checkout = next(step for step in verify['steps'] if step.get('uses', '').startswith('actions/checkout@'))
    assert checkout['with']['ref'] == '${{ inputs.ref || github.sha }}'
    identity = next(step for step in verify['steps'] if step.get('name') == 'Verify checkout identity')
    assert identity['env']['EXPECTED_SHA'] == '${{ inputs.ref || github.sha }}'
    assert 'git rev-parse HEAD' in identity['run']
    assert any(step.get('run') == 'npm run verify' for step in verify['steps'])


@pytest.mark.parametrize(('name', 'release_job', 'ref'), [
    ('release-on-main.yml', 'bump', '${{ github.sha }}'),
    ('publish-npm.yml', 'publish', '${{ inputs.expected_sha }}'),
])
def test_release_jobs_require_successful_read_only_matrix(name, release_job, ref):
    jobs = workflow(name)['jobs']
    gate = jobs['verify']
    assert gate['uses'] == './.github/workflows/ci.yml'
    assert gate['with']['ref'] == ref
    assert gate['permissions'] == {'contents': 'read'}
    assert 'continue-on-error' not in gate
    release = jobs[release_job]
    assert release['needs'] == 'verify'
    # Default success() must remain active: no override after failed/skipped CI.
    for expression in ('always(', 'failure(', 'cancelled('):
        assert expression not in release.get('if', '')
    checkout = next(step for step in release['steps'] if step.get('uses', '').startswith('actions/checkout@'))
    assert checkout['with']['ref'] == ref


def test_test_and_workflow_only_changes_do_not_trigger_npm_release():
    paths = workflow('release-on-main.yml')['on']['push']['paths']
    assert 'src/**' in paths
    assert 'README.md' in paths
    assert not any(path.startswith(('tests', '.github', 'docs/')) for path in paths)
    assert 'requirements-dev.txt' not in paths
