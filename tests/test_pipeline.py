import copy
import json
from pathlib import Path
import tempfile
import unittest
from pipeline.core import canonical, compile_queries, evaluate, extract, replay, retrieve

DOCS = [{'id': 'seed-1', 'title': 'Urban flood prediction', 'abstract': 'Flood prediction uses machine learning.'}]

def registry():
    result = extract(DOCS)
    for term in result['terms']:
        if term['preferred_label'] in ('urban', 'flood'):
            term.update(status='approved', concept_group=term['preferred_label'],
                        decision={'reviewer': 'fixture', 'rationale': 'Synthetic test'})
    return result

SPEC = {'strategy': 'concept_groups', 'groups': ['urban', 'flood']}

class PipelineTests(unittest.TestCase):
    def test_extraction_deterministic_with_evidence(self):
        self.assertEqual(canonical(extract(DOCS)), canonical(extract(DOCS)))
        term = next(t for t in extract(DOCS)['terms'] if t['preferred_label'] == 'urban flood')
        self.assertEqual(term['evidence'][0]['document_id'], 'seed-1')
        self.assertEqual(term['status'], 'proposed')

    def test_review_required(self):
        with self.assertRaises(ValueError): compile_queries(extract(DOCS), SPEC)
        r = registry(); next(t for t in r['terms'] if t['status'] == 'approved')['decision'] = None
        with self.assertRaises(ValueError): compile_queries(r, SPEC)

    def test_group_logic_and_expansion(self):
        r = registry()
        next(t for t in r['terms'] if t['preferred_label'] == 'flood')['variants'] = ['flooding']
        plan = compile_queries(r, SPEC)
        self.assertEqual(len(plan['requests']), 2)
        self.assertTrue(all(' AND ' in q['params']['search'] for q in plan['requests']))
        self.assertEqual(len(compile_queries(r, dict(SPEC, strategy='all_or'))['requests']), 3)
        with self.assertRaises(ValueError): compile_queries(r, dict(SPEC, max_requests=1))

    def test_retrieve_resume_replay_and_tamper(self):
        plan = compile_queries(registry(), SPEC)
        calls = []
        def fetch(params):
            calls.append(params['cursor'])
            if len(calls) == 2: raise OSError('interrupted')
            return canonical({'results': [{'id': 'https://openalex.org/W1'}], 'meta': {'next_cursor': 'next'}})
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(OSError): retrieve(plan, d, fetch)
            with self.assertRaises(ValueError): replay(d)
            def finish(params):
                self.assertEqual(params['cursor'], 'next')
                return canonical({'results': [{'id': 'https://openalex.org/W1'}, {'id': 'https://openalex.org/W2'}], 'meta': {'next_cursor': None}})
            corpus = retrieve(plan, d, finish)
            self.assertEqual(len(corpus), 2)
            self.assertEqual(corpus, replay(d))
            self.assertEqual(corpus, retrieve(plan, d, lambda _: self.fail('should use archive')))
            Path(d, 'page-000000.json').write_text('{}')
            with self.assertRaises(ValueError): replay(d)

    def test_repeated_cursor_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                retrieve(compile_queries(registry(), SPEC), d, lambda p: canonical({'results': [{'id': 'W1'}], 'meta': {'next_cursor': '*'}}))

    def test_evaluation_excludes_seeds_and_ineligible(self):
        corpus = [{'work': {'id': 'W1'}}]
        benchmark = [{'id': 'W1', 'relevant': True, 'eligible': True, 'split': 'held_out', 'sampled': True},
                     {'id': 'W2', 'relevant': True, 'eligible': False, 'split': 'held_out'},
                     {'id': 'W3', 'relevant': True, 'eligible': True, 'split': 'seed'}]
        result = evaluate(corpus, benchmark)
        self.assertEqual(result['known_paper_recall'], 1)
        self.assertEqual(result['sample_precision'], 1)

if __name__ == '__main__': unittest.main()
