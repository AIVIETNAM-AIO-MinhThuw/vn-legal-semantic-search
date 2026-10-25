import csv
import importlib.util
import json
from pathlib import Path

import pytest


def test_keyword_report_counts_segmented_words_and_preserves_queries(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1]/'scripts/check_query_keyword_length.py'
    spec = importlib.util.spec_from_file_location('keyword_check', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Segmenter:
        def word_segment(self, text):
            return [text.replace('người lao động', 'người_lao_động')]

    monkeypatch.setattr(module, 'load_segmenter', lambda settings: Segmenter())
    query_file = tmp_path/'queries.csv'
    original = 'quyền của người lao động !'
    with query_file.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerows([['query_id', 'query_type', 'query'],
                          ['Q1', 'keyword', original],
                          ['Q2', 'keyword', 'một hai ba bốn năm'],
                          ['Q3', 'natural', 'Câu này không tính?']])
    config = tmp_path/'bm25.yaml'
    config.write_text('segmenter:\n  revision: test-revision\n', encoding='utf-8')
    output = tmp_path/'report'
    monkeypatch.setattr(module.sys, 'argv', ['check', '--queries', str(query_file),
                        '--config', str(config), '--output', str(output)])
    module.main()
    with (output/'keyword_word_count.csv').open(encoding='utf-8', newline='') as stream:
        result = list(csv.DictReader(stream))
    assert [(r['query_id'], int(r['n_words']), r['flag']) for r in result] == [
        ('Q1', 3, ''), ('Q2', 5, 'keyword_over_4_words')]
    assert result[0]['query'] == original
    assert json.loads((output/'summary.json').read_text(encoding='utf-8'))['over_4_words'] == 1
    with pytest.raises(FileExistsError):
        module.main()
