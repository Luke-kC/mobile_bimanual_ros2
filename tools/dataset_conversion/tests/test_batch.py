import json
from pathlib import Path

import yaml

from tools.dataset_conversion.batch import discover, input_signature, existing_current, run_batch


def fixture(tmp_path):
    rec = tmp_path / 'recordings'
    ep = rec / 'same_task' / 'episode_20261026T000000Z_12345678'
    bag = ep / 'recording'
    bag.mkdir(parents=True)
    (bag / 'recording_0.mcap').write_bytes(b'example')
    (ep / 'metadata.yaml').write_text(yaml.safe_dump({'recording_valid': True, 'result': 'aborted'}))
    schema = tmp_path / 'schema.yaml'
    schema.write_text('schema_version: 1\n')
    return rec, ep, schema


def test_discovery_and_task_filter(tmp_path):
    rec, ep, _ = fixture(tmp_path)
    assert [x.path for x in discover(rec)] == [ep]
    assert discover(rec, 'different') == []
    assert len(discover(rec, 'same_task')) == 1


def test_signature_changes_with_inputs(tmp_path):
    rec, ep, schema = fixture(tmp_path)
    item = discover(rec)[0]
    before = input_signature(item, schema, 'diagnostic')
    schema.write_text('schema_version: 2\n')
    assert input_signature(item, schema, 'diagnostic') != before
    before = input_signature(item, schema, 'diagnostic')
    (ep / 'recording' / 'recording_0.mcap').write_bytes(b'changed bytes')
    assert input_signature(item, schema, 'diagnostic') != before


def test_skip_and_include_invalid(tmp_path):
    rec, ep, schema = fixture(tmp_path)
    (ep / 'metadata.yaml').write_text('recording_valid: false\nresult: aborted\n')
    kwargs = dict(recordings=rec, output_root=tmp_path / 'out', schema=schema, dry_run=True)
    assert run_batch(**kwargs)['skipped_invalid'] == 1
    assert run_batch(**kwargs, include_invalid=True)['skipped_invalid'] == 0


def test_completion_marker(tmp_path):
    rec, ep, schema = fixture(tmp_path)
    item = discover(rec)[0]
    fingerprint = input_signature(item, schema, 'diagnostic')
    out = tmp_path / 'out'
    out.mkdir()
    (out / 'conversion.json').write_text(json.dumps({'completed': True, 'fingerprint': fingerprint}))
    (out / 'report.json').write_text(json.dumps({'written_rows': 2}))
    (out / 'samples.jsonl').write_text('{}\n')
    (out / 'schema.yaml').write_text('foo: bar')
    assert existing_current(out, fingerprint)
    assert not existing_current(out, 'different')
    (out / 'samples.jsonl').unlink()
    assert not existing_current(out, fingerprint)


def test_batch_skip_and_atomic_rebuild(tmp_path, monkeypatch):
    rec, ep, schema = fixture(tmp_path)
    import tools.dataset_conversion.batch as batch
    called = []
    def fake_convert(bag, schema_path, output, *, profile, metadata, progress):
        called.append(str(bag))
        output.mkdir()
        (output / 'samples.jsonl').write_text('{"ok":1}\n')
        (output / 'schema.yaml').write_text('schema_version: 1\n')
        (output / 'report.json').write_text('{"written_rows":1}')
        return {'written_rows': 1}
    monkeypatch.setattr(batch, 'convert', fake_convert)
    out = tmp_path / 'out'
    params = dict(recordings=rec, output_root=out, schema=schema)
    assert batch.run_batch(**params)['converted'] == 1
    assert batch.run_batch(**params)['skipped_current'] == 1
    schema.write_text('schema_version: 2\n')
    assert batch.run_batch(**params)['converted'] == 1
    assert len(called) == 2
    assert batch.run_batch(**params, force=True)['converted'] == 1
