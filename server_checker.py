#!/usr/bin/env python3
"""
Server Access Tester
Measures file access latency on a server over time and generates analysis reports.
"""

import os
import sys
import time
import statistics
from datetime import datetime

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


# ---------------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------------

def access_http(url, timeout=30):
    """Returns (success, elapsed_sec, status_code_or_none, error_or_none)."""
    start = time.perf_counter()
    try:
        if HAS_REQUESTS:
            resp = requests.head(url, timeout=timeout, allow_redirects=True)
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
    """Returns (success, elapsed_sec, file_size_or_none, error_or_none)."""
    start = time.perf_counter()
    try:
        stat = os.stat(path)
        elapsed = time.perf_counter() - start
        return True, elapsed, stat.st_size, None
    except Exception as exc:
        elapsed = time.perf_counter() - start
        return False, elapsed, None, str(exc)


def probe(target, timeout=30):
    """Auto-detect URL vs file path and measure access latency."""
    if target.startswith(('http://', 'https://', 'ftp://')):
        success, elapsed, extra, error = access_http(target, timeout)
    else:
        success, elapsed, extra, error = access_file(target, timeout)
    return success, elapsed, extra, error


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt_ms(seconds):
    """Format seconds as a human-readable string."""
    ms = seconds * 1000
    if ms < 1:
        return f"{ms*1000:.1f}µs"
    elif ms < 1000:
        return f"{ms:.1f}ms"
    else:
        return f"{seconds:.2f}s"


def fmt_duration(seconds):
    """Format a duration in human-readable form."""
    if seconds < 60:
        return f"{seconds:.0f} שניות"
    elif seconds < 3600:
        return f"{seconds/60:.1f} דקות"
    else:
        return f"{seconds/3600:.1f} שעות"


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def ask(prompt, validator=None, error_msg="קלט לא תקין, נסה שוב."):
    while True:
        try:
            raw = input(prompt).strip()
            if validator is None:
                return raw
            result = validator(raw)
            if result is not None:
                return result
            print(f"  ! {error_msg}")
        except (KeyboardInterrupt, EOFError):
            print("\nביטול.")
            sys.exit(0)


def parse_positive_int(s):
    try:
        n = int(s)
        return n if n >= 1 else None
    except ValueError:
        return None


def parse_duration_str(s):
    """Accept: 30, 30s, 5m, 1h — returns seconds as float or None."""
    s = s.strip().lower()
    multipliers = {'h': 3600, 'm': 60, 's': 1}
    for suffix, mult in multipliers.items():
        if s.endswith(suffix):
            try:
                return float(s[:-1]) * mult
            except ValueError:
                return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_positive_duration(s):
    d = parse_duration_str(s)
    return d if (d is not None and d > 0) else None


# ---------------------------------------------------------------------------
# Core test runner
# ---------------------------------------------------------------------------

def run_test(target, num_attempts, total_duration_sec):
    interval = total_duration_sec / (num_attempts - 1) if num_attempts > 1 else 0

    print()
    print("  ┌─────────────────────────────────────────────────────────┐")
    print("  │  מתחיל בדיקה                                           │")
    print("  ├─────────────────────────────────────────────────────────┤")
    print(f"  │  יעד:               {target[:38]:<38} │")
    print(f"  │  ניסיונות:          {num_attempts:<38} │")
    print(f"  │  משך כולל:          {fmt_duration(total_duration_sec):<38} │")
    print(f"  │  מרווח בין ניסיון:  {fmt_ms(interval):<38} │")
    print("  └─────────────────────────────────────────────────────────┘")
    print()
    print(f"  {'#':>4}  {'תוצאה':<6}  {'זמן גישה':>12}  {'ממוצע עד כה':>14}  {'שעה'}")
    print(f"  {'─'*60}")

    results = []
    test_start = time.time()

    for i in range(num_attempts):
        attempt_wall = time.time()
        success, elapsed, extra, error = probe(target)

        results.append({
            'attempt': i + 1,
            'timestamp': attempt_wall,
            'success': success,
            'elapsed': elapsed,
            'extra': extra,
            'error': error,
        })

        icon = "✓" if success else "✗"
        successes = [r['elapsed'] for r in results if r['success']]
        avg_str = fmt_ms(statistics.mean(successes)) if successes else "—"
        ts = datetime.fromtimestamp(attempt_wall).strftime('%H:%M:%S')
        print(f"  {i+1:>4}  {icon:<6}  {fmt_ms(elapsed):>12}  {avg_str:>14}  {ts}")

        if i < num_attempts - 1:
            elapsed_since = time.time() - attempt_wall
            wait = max(0.0, interval - elapsed_since)
            if wait > 0:
                time.sleep(wait)

    total_elapsed = time.time() - test_start
    print(f"\n  הבדיקה הסתיימה תוך {fmt_duration(total_elapsed)}\n")
    return results


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------

def generate_report(results, target):
    successes = [(i, r) for i, r in enumerate(results) if r['success']]
    failures  = [(i, r) for i, r in enumerate(results) if not r['success']]
    times     = [r['elapsed'] for _, r in successes]

    print("═" * 62)
    print("          ניתוח תוצאות בדיקת גישה לשרת")
    print("═" * 62)
    print(f"  יעד:              {target}")
    print(f"  סה\"כ ניסיונות:    {len(results)}")
    print(f"  הצלחות:           {len(successes)}")
    print(f"  כישלונות:         {len(failures)}")

    if times:
        avg    = statistics.mean(times)
        median = statistics.median(times)
        min_t  = min(times)
        max_t  = max(times)
        stdev  = statistics.stdev(times) if len(times) > 1 else 0.0

        print()
        print("  ─── זמני גישה ───────────────────────────────────────")
        print(f"  ממוצע:            {fmt_ms(avg)}")
        print(f"  חציון:            {fmt_ms(median)}")
        print(f"  מינימום:          {fmt_ms(min_t)}")
        print(f"  מקסימום:          {fmt_ms(max_t)}")
        print(f"  סטיית תקן:        {fmt_ms(stdev)}")

        top_n = min(5, len(successes))
        slowest = sorted(successes, key=lambda x: x[1]['elapsed'], reverse=True)[:top_n]
        print()
        print(f"  ─── {top_n} הגישות האיטיות ביותר ─────────────────────")
        for rank, (idx, r) in enumerate(slowest, 1):
            ts = datetime.fromtimestamp(r['timestamp']).strftime('%H:%M:%S')
            print(f"  #{rank}  ניסיון {idx+1:3d}  |  {fmt_ms(r['elapsed']):>10}  |  {ts}")

    if failures:
        print()
        print("  ─── גישות שנכשלו ────────────────────────────────────")
        for idx, r in failures[:10]:
            ts  = datetime.fromtimestamp(r['timestamp']).strftime('%H:%M:%S')
            err = (r['error'] or 'שגיאה לא ידועה')[:55]
            print(f"  ניסיון {idx+1:3d}  |  {ts}  |  {err}")
        if len(failures) > 10:
            print(f"  ... ועוד {len(failures) - 10} כישלונות")

    print("═" * 62)

    # ── Graph ──────────────────────────────────────────────────────────────
    if not HAS_MATPLOTLIB:
        print("\n  [הערה: matplotlib לא מותקן – גרף לא נוצר]")
        print("  הרץ:  pip install matplotlib")
        return

    if not times:
        print("\n  אין נתוני הצלחה ליצירת גרף.")
        return

    avg    = statistics.mean(times)
    median = statistics.median(times)

    success_dt  = [datetime.fromtimestamp(r['timestamp']) for _, r in successes]
    elapsed_ms  = [r['elapsed'] * 1000 for _, r in successes]
    failure_dt  = [datetime.fromtimestamp(r['timestamp']) for _, r in failures]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8), constrained_layout=True)
    fig.suptitle(f'ניתוח גישה לשרת\n{target}', fontsize=12, fontweight='bold')

    # — Time-series plot —
    ax1.plot(success_dt, elapsed_ms, color='steelblue', linewidth=1.2,
             marker='o', markersize=3.5, alpha=0.8, label='זמן גישה')
    ax1.axhline(y=avg * 1000, color='red', linestyle='--', linewidth=1.5,
                label=f'ממוצע: {fmt_ms(avg)}')
    ax1.axhline(y=median * 1000, color='green', linestyle=':', linewidth=1.5,
                label=f'חציון: {fmt_ms(median)}')

    # Mark failures on time axis
    for dt in failure_dt:
        ax1.axvline(x=dt, color='orange', linewidth=0.8, alpha=0.5)

    if failure_dt:
        ax1.axvline(x=failure_dt[0], color='orange', linewidth=0.8,
                    alpha=0.5, label='כישלון')

    ax1.set_ylabel('זמן גישה (ms)')
    ax1.set_title('זמני גישה לאורך הדגימה')
    ax1.legend(loc='upper right', fontsize=8)
    ax1.grid(True, alpha=0.25)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    fig.autofmt_xdate(rotation=30)

    # — Histogram —
    bins = min(30, max(5, len(times) // 2))
    ax2.hist(elapsed_ms, bins=bins, color='steelblue', edgecolor='white',
             linewidth=0.5, alpha=0.8)
    ax2.axvline(x=avg * 1000, color='red', linestyle='--', linewidth=1.5,
                label=f'ממוצע: {fmt_ms(avg)}')
    ax2.axvline(x=median * 1000, color='green', linestyle=':', linewidth=1.5,
                label=f'חציון: {fmt_ms(median)}')
    ax2.set_xlabel('זמן גישה (ms)')
    ax2.set_ylabel('מספר גישות')
    ax2.set_title('התפלגות זמני גישה')
    ax2.legend(loc='upper right', fontsize=8)
    ax2.grid(True, alpha=0.25)

    out_path = f"access_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"\n  גרף נשמר: {out_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║           Server Access Tester                       ║")
    print("  ║      בודק זמני גישה לקבצים בשרת                    ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()

    target = ask(
        "  הכנס נתיב לקובץ או URL:\n"
        "  (לדוגמה: http://server/file.txt  או  /mnt/share/file.txt)\n"
        "  > "
    )
    if not target:
        print("  לא הוזן נתיב. יוצא.")
        sys.exit(1)

    num_attempts = ask(
        "\n  כמה ניסיונות גישה לבצע? (לדוגמה: 20)\n"
        "  > ",
        validator=parse_positive_int,
        error_msg="הכנס מספר שלם חיובי (לדוגמה: 10)."
    )

    total_duration = ask(
        f"\n  תוך כמה זמן לבצע את {num_attempts} הניסיונות?\n"
        "  (לדוגמה: 60s = שניות, 5m = דקות, 1h = שעה)\n"
        "  > ",
        validator=parse_positive_duration,
        error_msg="הכנס ערך תקין כגון: 30s  5m  1h  או מספר בשניות."
    )

    interval = total_duration / (num_attempts - 1) if num_attempts > 1 else 0

    print()
    print("  ┌─── סיכום הגדרות ─────────────────────────────────────┐")
    print(f"  │  יעד:               {target[:38]:<38} │")
    print(f"  │  ניסיונות:          {num_attempts:<38} │")
    print(f"  │  משך כולל:          {fmt_duration(total_duration):<38} │")
    print(f"  │  מרווח בין ניסיון:  {fmt_ms(interval):<38} │")
    print("  └─────────────────────────────────────────────────────────┘")

    confirm = ask("\n  להתחיל בדיקה? (y/n): ")
    if confirm.lower() not in ('y', 'yes', 'כן', ''):
        print("  ביטול.")
        sys.exit(0)

    results = run_test(target, num_attempts, total_duration)
    generate_report(results, target)


if __name__ == '__main__':
    main()
