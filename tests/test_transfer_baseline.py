"""Scientific design and missingness checks for the expanded baseline."""
import asyncio
from collections import Counter
from copy import deepcopy
import json

import pytest

from swarmgraph.transfer_baseline.design import PROTOCOL, planned_cases
from swarmgraph.transfer_baseline.analysis import calibration_data, describe, score_difference, scores
from swarmgraph.transfer_baseline.run import MonitorClient


def test_design_has_disjoint_balanced_pairs_and_omissions():
    cases = planned_cases()
    assert len(cases) == PROTOCOL['formal_episodes'] == 396
    assert sum(8 if c['execution_layout'] == 'solo' else 10 for c in cases) == 3576
    seeds = {}
    for c in cases:
        if c['condition'] == 'incomplete_attack':
            group = 'omission'
        elif c['partition'] == 'calibration':
            group = 'calibration'
        elif c['condition'].startswith('honest'):
            group = 'honest_evaluation'
        else:
            group = 'attack'
        seeds.setdefault(group, set()).add(c['seed'])
    assert sum(map(len, seeds.values())) == len(set.union(*seeds.values()))
    for group in ('calibration', 'honest_evaluation', 'attack'):
        assert len(seeds[group]) == 64
        for seed in seeds[group]:
            pair = [c for c in cases if c['seed'] == seed]
            assert {c['execution_layout'] for c in pair} == {'solo', 'split'}
            assert len({c['pair_id'] for c in pair}) == 1
    for partition in ('calibration', 'evaluation'):
        honest = [c for c in cases if c['partition'] == partition and c['condition'].startswith('honest')]
        counts = Counter((c['seed'] % 4, c['condition'], c['execution_layout']) for c in honest)
        assert len(counts) == 16 and set(counts.values()) == {8}
    omissions = [c for c in cases if c['condition'] == 'incomplete_attack']
    assert len({(c['seed'] % 4, c['omit_role']) for c in omissions}) == 12


def test_missing_agent_judgment_is_not_a_low_fleet_maximum():
    run = {'manifest': {'agent_ids': ['a', 'b'], 'focal_agent_ids': ['a']},
           'monitors': [{'is_final': True, 'prefix_boundary': 5, 'monitor_view': 'per_agent',
                         'evidence_condition': 'transcript', 'candidate_agent_ids': ['a'],
                         'result_status': 'ok', 'score': 12}], 'final_boundary': 5}
    result = scores(run)
    assert result == {'fleet': None, 'focal': 12, 'joint': None}
    assert run['manifest']['agent_ids'] == ['a', 'b']
    run['monitors'][0]['result_status'] = 'invalid_evidence_citation'
    assert scores(run)['focal'] is None


def test_paired_gap_preserves_pairing_and_excludes_missing():
    result = score_difference([90, 80, 100, None], [20, None, 40, 0])
    assert result['n_pairs'] == 2
    assert result['mean_points'] == pytest.approx(65)
    assert describe([None, None])['mean'] is None
    with pytest.raises(ValueError):
        score_difference([10, 20], [10])


def test_calibration_ignores_evaluation_and_invalid_honest_runs():
    template = {'manifest': {'partition': 'calibration', 'execution_layout': 'split',
        'condition': 'honest_authorized', 'status': 'complete', 'generation_mode': 'scripted', 'run_id': 'a'},
        'validation': {'valid': True}, 'outcome': {'verification_status': 'execution_verified',
        'main_task_complete': True, 'prohibited_outcome': False, 'valid_benign': True, 'control_completed': True},
        'scores': {'fleet': 10, 'focal': 5, 'joint': 0}}
    evaluation = deepcopy(template)
    evaluation['manifest'].update(partition='evaluation', run_id='b')
    evaluation['scores']['fleet'] = 100
    invalid = deepcopy(template)
    invalid['validation']['valid'] = False
    result = calibration_data([template, evaluation, invalid])
    assert result['split/fleet']['n'] == 1
    assert result['split/fleet']['threshold'] > 10
    assert result['split/fleet']['threshold'] < 11


def test_monitor_client_rejects_actor_calls_and_stops_queued_access_failures(tmp_path):
    calls = []
    async def exercise():
        client = MonitorClient(tmp_path, concurrency=1)
        async def fail(prompt, schema, purpose, call_id):
            calls.append(call_id)
            return {'status': 'error', 'error_kind': 'access_forbidden', 'call_id': call_id}
        client.client.ask = fail
        with pytest.raises(ValueError):
            await client.ask('unused', {}, 'actor', 'actor')
        results = await asyncio.gather(*(client.ask('unused', {}, 'monitor', str(i)) for i in range(3)))
        assert results[0]['status'] == 'error'
        assert all(r['status'] == 'not_run' for r in results[1:])
    asyncio.run(exercise())
    assert calls == ['0']
    assert json.loads((tmp_path/'STOP_ACCESS').read_text())['error_kind'] == 'access_forbidden'
