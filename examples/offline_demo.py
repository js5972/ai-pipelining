"""Synthetic transport demo: no OpenAlex calls or real scholarly records."""
from pathlib import Path
from pipeline.core import canonical, compile_queries, extract, read, replay, retrieve, write

root = Path(__file__).resolve().parent
out = root.parent / '.runs' / 'offline-demo'
write(out / 'candidates.json', extract(read(root / 'documents.json')))
plan = compile_queries(read(root / 'registry.json'), read(root / 'query-spec.json'))
write(out / 'plan.json', plan)

def fixture(params):
    if params['cursor'] == '*':
        return canonical({'meta': {'next_cursor': 'fixture-page-2'}, 'results': [
            {'id': 'https://openalex.org/W000000001', 'title': 'SYNTHETIC urban flood fixture'}]})
    return canonical({'meta': {'next_cursor': None}, 'results': [
        {'id': 'https://openalex.org/W000000001', 'title': 'SYNTHETIC urban flood fixture'},
        {'id': 'https://openalex.org/W000000002', 'title': 'SYNTHETIC second fixture'}]})

corpus = retrieve(plan, out, fixture)
assert corpus == replay(out) and len(corpus) == 2
print(f'Offline demo: two pages, two unique synthetic works; verified replay in {out}')
