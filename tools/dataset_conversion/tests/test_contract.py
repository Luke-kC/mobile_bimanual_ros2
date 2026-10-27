from pathlib import Path
import pytest
from tools.dataset_conversion.schema import load_schema
from tools.dataset_conversion.alignment import Sample
from tools.dataset_conversion.convert import build

SCHEMA = Path(__file__).resolve().parents[3] / 'config/dataset/schema.yaml'

def test_schema():
    s = load_schema(SCHEMA)
    assert s['dataset']['fps'] == 30
    assert s['actions']['height_adjust']['semantics'] == 'event_target'

def test_missing_action_not_fabricated():
    schema = load_schema(SCHEMA)
    for spec in schema['observations'].values():
        spec['required'] = False
    streams = {'mode': [Sample(0, 'manipulation'), Sample(100_000_000, 'manipulation')]}
    rows, _, _ = build(schema, streams, 0, 100_000_000, profile='diagnostic')
    assert rows[0]['commands']['manipulation_right.authorized']['valid'] is False
    train, _, _ = build(schema, streams, 0, 100_000_000, profile='training')
    assert train == []
