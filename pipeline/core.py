"""Standard-library implementation; no model or API key needed for offline work."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

VERSION = '0.1.0'
STOP = set('a an and are as at be by for from in is it of on or that the this to was were with'.split())

def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(canonical(value))

def normalize(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())

def extract(documents, max_words=3):
    """Sentence-bounded ngrams; length-adjusted TF-IDF, lexical ties."""
    if not documents or len({d['id'] for d in documents}) != len(documents):
        raise ValueError('Require nonempty documents with unique IDs')
    counts, evidence = {}, {}
    for doc in sorted(documents, key=lambda d: d['id']):
        counts[doc['id']] = Counter()
        for section in ('title', 'abstract'):
            for passage in re.split(r'[.!?;\n]+', doc.get(section, '')):
                tokens = re.findall(r"[a-z]+(?:[-'][a-z]+)*", normalize(passage))
                for n in range(1, max_words + 1):
                    for i in range(len(tokens) - n + 1):
                        words = tokens[i:i+n]
                        if words[0] in STOP or words[-1] in STOP or any(w in STOP for w in words):
                            continue
                        term = ' '.join(words)
                        counts[doc['id']][term] += 1
                        item = {'document_id': doc['id'], 'section': section, 'passage': passage.strip()}
                        evidence.setdefault(term, [])
                        if item not in evidence[term]:
                            evidence[term].append(item)
    terms = []
    for term in sorted(evidence):
        df = sum(term in c for c in counts.values())
        score = sum((1 + math.log(c[term])) for c in counts.values() if c[term]) * (1 + math.log((1+len(documents))/(1+df))) * len(term.split())
        terms.append({'term_id': digest(term.encode())[:16], 'preferred_label': term,
                      'variants': [], 'concept_group': None, 'status': 'proposed',
                      'score': round(score, 8), 'evidence': evidence[term], 'decision': None})
    terms.sort(key=lambda t: (-t['score'], t['preferred_label']))
    return {'version': 1, 'algorithm': 'sentence-ngram-tfidf-v1', 'max_words': max_words,
            'documents_sha256': digest(canonical(documents)), 'terms': terms}

def compile_queries(registry, spec):
    if spec.get('strategy') not in ('concept_groups', 'all_or'):
        raise ValueError('strategy must be concept_groups or all_or')
    groups = spec.get('groups', [])
    if not groups or len(set(groups)) != len(groups):
        raise ValueError('Require unique nonempty groups')
    selected = {g: set() for g in groups}
    ids, labels = set(), set()
    for term in registry['terms']:
        if term['term_id'] in ids or normalize(term['preferred_label']) in labels:
            raise ValueError('Duplicate term ID or label')
        ids.add(term['term_id']); labels.add(normalize(term['preferred_label']))
        if term['status'] != 'approved':
            continue
        if not term.get('evidence') or not isinstance(term.get('decision'), dict) or not all(term['decision'].get(k) for k in ('reviewer', 'rationale')):
            raise ValueError('Approved terms require evidence and reviewer/rationale')
        group = term.get('concept_group')
        if group not in selected:
            continue
        for label in [term['preferred_label']] + term.get('variants', []):
            label = normalize(label)
            if not re.fullmatch(r"[a-z0-9]+(?:[ '-][a-z0-9]+)*", label):
                raise ValueError('Unsupported search phrase: ' + label)
            selected[group].add(label)
    if any(not terms for terms in selected.values()):
        raise ValueError('Each required group needs approved terms')
    # Enumerating phrase combinations preserves AND across groups and OR within groups.
    combinations = itertools.product(*(sorted(selected[g]) for g in groups)) if spec['strategy'] == 'concept_groups' else ((t,) for t in sorted(set.union(*selected.values())))
    requests = []
    filters = spec.get('filters', {})
    allowed = {'from_publication_date', 'to_publication_date', 'language', 'type'}
    if set(filters) - allowed or any(not isinstance(v, str) or not re.fullmatch(r'[a-z0-9-]+', v) for v in filters.values()):
        raise ValueError('Unsupported filter or filter value')
    for phrases in combinations:
        if len(requests) >= spec.get('max_requests', 100):
            raise ValueError('Query expansion exceeds max_requests')
        params = {'search': ' AND '.join('"' + p + '"' for p in phrases), 'per-page': 100}
        if filters:
            params['filter'] = ','.join(k + ':' + filters[k] for k in sorted(filters))
        requests.append({'query_id': digest(canonical(params))[:16], 'params': params})
    return {'version': 1, 'compiler': VERSION, 'registry_sha256': digest(canonical(registry)),
            'spec': spec, 'requests': requests}

def fetch(params):
    key = os.environ.get('OPENALEX_API_KEY')
    if key:
        params = dict(params, api_key=key)
    for attempt in range(4):
        try:
            with urlopen('https://api.openalex.org/works?' + urlencode(params), timeout=60) as response:
                return response.read()
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise RuntimeError(f'OpenAlex HTTP {error.code}; request URL omitted to protect credentials') from None
            delay = error.headers.get('Retry-After', '')
            time.sleep(min(float(delay) if delay.isdigit() else 2**attempt, 60))

def retrieve(plan, directory, fetcher=fetch):
    root = Path(directory); root.mkdir(parents=True, exist_ok=True)
    plan_hash = digest(canonical(plan))
    manifest_path = root / 'manifest.json'
    if manifest_path.exists():
        manifest = read(manifest_path)
        if manifest['plan_sha256'] != plan_hash:
            raise ValueError('Run directory belongs to another query plan')
        replay(root, require_complete=False)
    else:
        try:
            commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL, text=True).strip()
            dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip())
        except subprocess.CalledProcessError:
            commit, dirty = None, True
        manifest = {'version': 1, 'pipeline_version': VERSION, 'python': sys.version,
                    'git_commit': commit, 'git_dirty': dirty, 'plan_sha256': plan_hash,
                    'plan': plan, 'pages': [], 'complete': False}
        write(manifest_path, manifest)
    for query in plan['requests']:
        saved = [p for p in manifest['pages'] if p['query_id'] == query['query_id']]
        cursor = saved[-1]['next_cursor'] if saved else '*'
        seen = {p['cursor'] for p in saved}
        while cursor is not None:
            if cursor in seen:
                raise ValueError('Repeated pagination cursor')
            params = dict(query['params'], cursor=cursor)
            raw = fetcher(params)
            data = json.loads(raw)
            if not isinstance(data.get('results'), list) or not isinstance(data.get('meta'), dict) or 'next_cursor' not in data['meta']:
                raise ValueError('Invalid OpenAlex page')
            next_cursor = data['meta']['next_cursor']
            if not data['results'] and next_cursor is not None:
                raise ValueError('Empty nonterminal page')
            filename = f'page-{len(manifest["pages"]):06d}.json'
            (root / filename).write_bytes(raw)
            manifest['pages'].append({'file': filename, 'sha256': digest(raw), 'query_id': query['query_id'],
                                      'cursor': cursor, 'next_cursor': next_cursor, 'params': params,
                                      'retrieved_at': datetime.now(timezone.utc).isoformat()})
            write(manifest_path, manifest)
            seen.add(cursor); cursor = next_cursor
    manifest['complete'] = True
    write(manifest_path, manifest)
    return replay(root)

def replay(directory, require_complete=True):
    root = Path(directory); manifest = read(root / 'manifest.json')
    if require_complete and not manifest['complete']:
        raise ValueError('Retrieval is incomplete')
    if digest(canonical(manifest['plan'])) != manifest['plan_sha256']:
        raise ValueError('Query plan checksum mismatch')
    works, membership = {}, {}
    for page in manifest['pages']:
        if Path(page['file']).name != page['file']:
            raise ValueError('Invalid archive filename')
        raw = (root / page['file']).read_bytes()
        if digest(raw) != page['sha256']:
            raise ValueError('Archive checksum mismatch')
        for work in json.loads(raw)['results']:
            ident = work['id']
            works.setdefault(ident, work)
            membership.setdefault(ident, set()).add(page['query_id'])
    result = [{'work': works[i], 'query_ids': sorted(membership[i])} for i in sorted(works)]
    if require_complete:
        write(root / 'corpus.json', result)
    return result

def evaluate(corpus, benchmark):
    retrieved = {r['work']['id'] for r in corpus}
    eligible = {b['id'] for b in benchmark if b['relevant'] and b['eligible'] and b['split'] == 'held_out'}
    reviewed = [b for b in benchmark if b['id'] in retrieved and b.get('sampled', False)]
    return {'held_out_eligible': len(eligible), 'held_out_found': len(eligible & retrieved),
            'known_paper_recall': len(eligible & retrieved)/len(eligible) if eligible else None,
            'sample_reviewed': len(reviewed),
            'sample_precision': sum(b['relevant'] for b in reviewed)/len(reviewed) if reviewed else None,
            'retrieved': len(retrieved)}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name, fields in [('extract', ['documents', 'output']), ('compile', ['registry', 'spec', 'output']),
                         ('retrieve', ['plan', 'directory']), ('replay', ['directory']),
                         ('evaluate', ['corpus', 'benchmark', 'output'])]:
        p = sub.add_parser(name)
        for field in fields:
            p.add_argument(field)
    args = parser.parse_args()
    try:
        if args.command == 'extract': write(args.output, extract(read(args.documents)))
        elif args.command == 'compile': write(args.output, compile_queries(read(args.registry), read(args.spec)))
        elif args.command == 'retrieve': print(f'{len(retrieve(read(args.plan), args.directory))} unique works')
        elif args.command == 'replay': print(f'{len(replay(args.directory))} unique works (verified replay)')
        else: write(args.output, evaluate(read(args.corpus), read(args.benchmark)))
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, f'Error: {error}\n')
