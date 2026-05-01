#!/usr/bin/env python3
"""
Server Access Tester – Flask web application.
Run:  python app.py
Then open http://localhost:5000 in your browser.
"""

import json
import os
import statistics
import time
from datetime import datetime

from flask import Flask, Response, render_template, request, stream_with_context

try:
    import requests as req_lib
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------------

def access_http(url, timeout=30):
    start = time.perf_counter()
    try:
        if HAS_REQUESTS:
            resp = req_lib.head(url, timeout=timeout, allow_redirects=True)
            elapsed = time.perf_counter() - start
            return True, elapsed, resp.status_code, None
        else:
            import urllib.request
            req = urllib.request.Request(url, method='HEAD')
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed = time.perf_counter() - start
                return True, elapsed, resp.status, None
    except Exception as exc:
        elapsed = time.perf_counter() - start
        return False, elapsed, None, str(exc)


def access_file(path, timeout=30):
    start = time.perf_counter()
    try:
        stat = os.stat(path)
        elapsed = time.perf_counter() - start
        return True, elapsed, stat.st_size, None
    except Exception as exc:
        elapsed = time.perf_counter() - start
        return False, elapsed, None, str(exc)


def probe(target, timeout=30):
    if target.startswith(('http://', 'https://', 'ftp://')):
        success, elapsed, extra, error = access_http(target, timeout)
    else:
        success, elapsed, extra, error = access_file(target, timeout)
    return success, elapsed, error


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def compute_stats(results):
    successes = [r for r in results if r['success']]
    times = [r['elapsed'] for r in successes]
    if not times:
        return {
            'count': len(results),
            'success_count': 0,
            'failure_count': len(results),
            'avg': 0, 'median': 0, 'min': 0, 'max': 0, 'stdev': 0,
            'slowest': [],
        }
    return {
        'count': len(results),
        'success_count': len(successes),
        'failure_count': len(results) - len(successes),
        'avg':    statistics.mean(times),
        'median': statistics.median(times),
        'min':    min(times),
        'max':    max(times),
        'stdev':  statistics.stdev(times) if len(times) > 1 else 0.0,
        'slowest': sorted(
            [{'attempt': r['attempt'], 'elapsed': r['elapsed'], 'timestamp': r['timestamp']}
             for r in successes],
            key=lambda x: x['elapsed'], reverse=True
        )[:5],
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/test')
def run_test():
    target = request.args.get('target', '').strip()
    try:
        attempts = max(1, int(request.args.get('attempts', 10)))
        duration = max(0.1, float(request.args.get('duration', 60)))
        timeout  = max(1,   int(request.args.get('timeout', 30)))
    except (ValueError, TypeError):
        return Response('Bad parameters', status=400)

    if not target:
        return Response('Missing target', status=400)

    def generate():
        interval = duration / (attempts - 1) if attempts > 1 else 0
        results  = []

        yield _sse('start', {
            'attempts': attempts,
            'duration': duration,
            'interval': interval,
        })

        for i in range(attempts):
            wall = time.time()
            success, elapsed, error = probe(target, timeout)

            result = {
                'attempt':   i + 1,
                'timestamp': wall,
                'success':   success,
                'elapsed':   elapsed,
                'error':     error,
            }
            results.append(result)

            times_so_far = [r['elapsed'] for r in results if r['success']]
            avg_so_far = statistics.mean(times_so_far) if times_so_far else None

            yield _sse('progress', {
                'result':     result,
                'avg_so_far': avg_so_far,
            })

            if i < attempts - 1:
                wait = max(0.0, interval - (time.time() - wall))
                if wait > 0:
                    time.sleep(wait)

        yield _sse('done', {
            'stats':   compute_stats(results),
            'results': results,
        })

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


def _sse(event_type, data):
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print("=" * 52)
    print("  Server Access Tester")
    print("  פתח בדפדפן:  http://localhost:5000")
    print("=" * 52)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
