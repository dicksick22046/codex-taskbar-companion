"""Check reviewed prices against the official public Standard pricing table."""
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from codex_taskbar.pricing import RATES
from codex_taskbar.pricing_sync import fetch_official_standard_prices

REVIEWED = ROOT / 'scripts/standard_model_ids.txt'
HEADING = '### Standard pricing data'
HEADER = ('Model', 'Short context input', 'Short context cached input', 'Short context cache writes',
          'Short context output', 'Long context input', 'Long context cached input',
          'Long context cache writes', 'Long context output')


def cells(line):
    return tuple(cell.strip() for cell in line.strip().strip('|').split('|'))


def standard_prices(markdown):
    sections = markdown.split(HEADING)
    if len(sections) != 2: raise ValueError('Official Standard pricing section changed')
    lines = sections[1].splitlines()
    start = next((i for i, line in enumerate(lines) if cells(line) == HEADER), None)
    if start is None or start + 1 >= len(lines) or not all(cell == '---' for cell in cells(lines[start + 1])):
        raise ValueError('Official Standard pricing columns changed')
    rows = {}
    for line in lines[start + 2:]:
        if not line.startswith('|'): break
        fields = cells(line)
        if len(fields) != len(HEADER): raise ValueError('Official Standard pricing row changed')
        name = fields[0].removesuffix(' (<272K context length)')
        try: rows[name] = tuple(None if price == '-' else Decimal(price.removeprefix('$')) for price in fields[1:])
        except InvalidOperation as exc: raise ValueError(f'Official Standard price is invalid for {name}') from exc
    return rows


def differences(rows, reviewed):
    problems = []
    for name in sorted(rows.keys() - reviewed): problems.append(f'New Standard model to review: {name}')
    for name in sorted(reviewed - rows.keys()): problems.append(f'Reviewed Standard model disappeared: {name}')
    for name, rates in sorted(RATES.items()):
        if len(rows.get(name, ())) == 5:
            expected = tuple(float(value) if value is not None else None for value in rates[:4]) + (rates[4],)
        else:
            expected = tuple(None if value is None else Decimal(str(value)) for value in rates[:4])
            expected += tuple(None if value is None else expected[i] * factor for i, (value, factor) in enumerate(zip(expected[:4], (2, 2, 2, Decimal('1.5'))))) if rates[4] else (None,) * 4
        if rows.get(name) != expected: problems.append(f'Official Standard rates changed for {name}: {rows.get(name)}')
    return problems


def main():
    rows = fetch_official_standard_prices()
    reviewed = set(REVIEWED.read_text(encoding='utf-8').splitlines())
    problems = differences(rows, reviewed)
    if problems:
        print('\n'.join(problems)); raise SystemExit(1)
    print(f'Official Standard prices match {len(RATES)} supported models; {len(reviewed)} model IDs reviewed.')


if __name__ == '__main__': main()
