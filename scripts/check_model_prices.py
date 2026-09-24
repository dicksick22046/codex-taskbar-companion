"""Check reviewed prices against the official public Standard pricing table."""
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from codex_taskbar.pricing import RATES

SOURCE = 'https://developers.openai.com/api/docs/pricing.md'
REVIEWED = ROOT / 'scripts/standard_model_ids.txt'
HEADING = '### Standard pricing data'
HEADER = ('Model', 'Short context input', 'Short context cached input',
          'Short context cache writes', 'Short context output',
          'Long context input', 'Long context cached input',
          'Long context cache writes', 'Long context output')


def cells(line):
    return tuple(cell.strip() for cell in line.strip().strip('|').split('|'))


def standard_prices(markdown):
    sections = markdown.split(HEADING)
    if len(sections) != 2:
        raise ValueError('Official Standard pricing section changed')
    lines = sections[1].splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if cells(line) == HEADER)
    except StopIteration as exc:
        raise ValueError('Official Standard pricing columns changed') from exc
    if start + 1 >= len(lines) or not all(cell == '---' for cell in cells(lines[start+1])):
        raise ValueError('Official Standard pricing separator changed')
    rows = {}
    for line in lines[start+2:]:
        if not line.startswith('|'):
            break
        fields = cells(line)
        if len(fields) != len(HEADER):
            raise ValueError('Official Standard pricing row changed')
        name = fields[0].removesuffix(' (<272K context length)')
        if not name or name in rows:
            raise ValueError('Official Standard model IDs are ambiguous')
        try:
            rows[name] = tuple(None if price == '-' else Decimal(price.removeprefix('$')) for price in fields[1:])
        except InvalidOperation as exc:
            raise ValueError(f'Official Standard price is invalid for {name}') from exc
    if len(rows) < len(RATES) or not set(RATES) <= rows.keys():
        raise ValueError('Official Standard pricing table is incomplete')
    return rows


def differences(rows, reviewed):
    problems = []
    for name in sorted(rows.keys() - reviewed):
        problems.append(f'New Standard model to review: {name}')
    for name in sorted(reviewed - rows.keys()):
        problems.append(f'Reviewed Standard model disappeared: {name}')
    for name, (input_rate, cached_rate, write_rate, output_rate, threshold) in sorted(RATES.items()):
        short = tuple(None if rate is None else Decimal(str(rate))
                      for rate in (input_rate, cached_rate, write_rate, output_rate))
        long = tuple(None if rate is None else rate * factor for rate, factor in zip(
            short, (Decimal(2), Decimal(2), Decimal(2), Decimal('1.5')))) if threshold else (None,) * 4
        if rows[name] != short + long:
            problems.append(f'Official Standard rates changed for {name}: {rows[name]}')
    return problems


def main():
    request = urllib.request.Request(SOURCE, headers={'Accept': 'text/markdown',
                                                        'User-Agent': 'CodexTaskbarCompanion-price-audit'})
    with urllib.request.urlopen(request, timeout=15) as response:
        markdown = response.read(512001)
    if len(markdown) > 512000:
        raise ValueError('Official pricing page exceeds the audit size limit')
    rows = standard_prices(markdown.decode('utf-8'))
    reviewed = set(REVIEWED.read_text(encoding='utf-8').splitlines())
    problems = differences(rows, reviewed)
    if problems:
        print('\n'.join(problems))
        raise SystemExit(1)
    print(f'Official Standard prices match {len(RATES)} supported models; '
          f'{len(reviewed)} model IDs reviewed.')


if __name__ == '__main__':
    main()
