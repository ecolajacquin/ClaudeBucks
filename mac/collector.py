"""Read cached monthly Claude Code credits from ~/.claude.json; no HTTP calls."""
import argparse
import json
import math
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CLAUDE_CONFIG = Path.home() / '.claude.json'
STALE_AFTER_SECONDS = 15 * 60


@dataclass
class ClaudeBucks:
    used: float
    budget: float
    fetched_at: datetime
    age_seconds: float

    @property
    def remaining(self):
        return max(0.0, self.budget - self.used)

    @property
    def percentage(self):
        return min(100.0, 100 * self.used / self.budget)

    @property
    def stale(self):
        return self.age_seconds > STALE_AFTER_SECONDS


def collect(budget: float | None = None) -> ClaudeBucks:
    try:
        with CLAUDE_CONFIG.open(encoding='utf-8') as f:
            data = json.load(f)
        cache = data['cachedUsageUtilization']
        utilization = cache['utilization']
        spend = utilization.get('spend')
        if spend and spend.get('used') and spend.get('limit'):
            u = spend['used']
            b = spend['limit']
            if u['currency'] != 'USD' or b['currency'] != 'USD':
                raise ValueError('Expected USD credits')
            used = int(u['amount_minor']) / (10 ** int(u['exponent']))
            cached_budget = int(b['amount_minor']) / (10 ** int(b['exponent']))
        else:
            extra = utilization['extra_usage']
            if not extra.get('is_enabled') or extra.get('currency') != 'USD':
                raise ValueError('USD usage credits unavailable')
            divisor = 10 ** int(extra['decimal_places'])
            used = int(extra['used_credits']) / divisor
            cached_budget = int(extra['monthly_limit']) / divisor
        effective_budget = cached_budget if budget is None else budget
        if (not math.isfinite(used) or not math.isfinite(effective_budget)
                or used < 0 or effective_budget <= 0):
            raise ValueError('Invalid monetary values')
        fetched_ms = int(cache['fetchedAtMs'])
        return ClaudeBucks(
            used=used,
            budget=effective_budget,
            fetched_at=datetime.fromtimestamp(fetched_ms / 1000),
            age_seconds=max(0.0, time.time() - fetched_ms / 1000),
        )
    except (OSError, KeyError, ValueError, TypeError, OverflowError) as exc:
        raise RuntimeError(f'Claude Code cache unavailable: {exc}') from exc


def main():
    parser = argparse.ArgumentParser(description='Test local Claude Bucks collector')
    parser.add_argument('--budget', type=float, default=None)
    args = parser.parse_args()
    try:
        reading = collect(args.budget)
    except RuntimeError as exc:
        parser.exit(1, f'{exc}\n')
    print(f'Used: C{reading.used:.2f}')
    print(f'Left: C{reading.remaining:.2f}')
    print(f'Budget: C{reading.budget:.2f}')
    print(f'Usage: {reading.percentage:.2f}%')
    print(f'Updated: {reading.fetched_at.isoformat()}')
    print('Status:', 'STALE' if reading.stale else 'FRESH')


if __name__ == '__main__':
    main()
