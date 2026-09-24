"""Standard API equivalent prices; reviewed 2026-09-24, not subscription billing.

Source: https://developers.openai.com/api/docs/pricing
Rates are USD per million tokens followed by the long-input threshold, if any.
Model identifiers match exactly.
"""

RATES = {
    'gpt-6-astra': (10., 1., 12.5, 50., 272000),
    'gpt-6-sol': (2., .2, 2.5, 10., 272000),
    'gpt-6-luna': (.1, .01, .125, .5, 272000),
    'gpt-5.6-sol': (4., .4, 5., 20., 272000),
    'gpt-5.6-terra': (2., .2, 2.5, 12., 272000),
    'gpt-5.5': (5., .5, None, 30., 272000),
    'gpt-5.4': (2.5, .25, None, 15., 272000),
    'gpt-5.4-mini': (.75, .075, None, 4.5, None),
}
COUNTERS = ('total_tokens', 'input_tokens', 'cached_input_tokens', 'output_tokens')


def estimate_usd(model, usage):
    """Price one verified model call; incomplete or inconsistent inputs stay unknown."""
    rates = RATES.get(model)
    if rates is None or not isinstance(usage, dict):return None
    if any(type(usage.get(key)) is not int or usage[key] < 0 for key in COUNTERS):return None
    total, inputs, cached, outputs = (usage[key] for key in COUNTERS)
    written = usage.get('cache_write_input_tokens', 0 if rates[2] is None else None)
    if type(written) is not int or written < 0 or cached + written > inputs:return None
    if total != inputs + outputs:return None
    input_rate, cache_rate, write_rate, output_rate, threshold = rates
    input_factor, output_factor = (2., 1.5) if threshold is not None and inputs > threshold else (1., 1.)
    # Models without a separate write rate price these input tokens as ordinary input.
    cost = ((inputs-cached-written)*input_rate + cached*cache_rate
            + written*(input_rate if write_rate is None else write_rate))*input_factor
    return (cost + outputs*output_rate*output_factor)/1_000_000


def usage_cost(model, current, previous, step):
    """Only price a cumulative delta proven to be exactly one reported call."""
    if not isinstance(step, dict):return None
    reset = (previous is not None and type(current.get('total_tokens')) is int
             and type(previous.get('total_tokens')) is int
             and current['total_tokens'] < previous['total_tokens'])
    if reset and any(current.get(key, 0) != step.get(key, 0)
                     for key in COUNTERS + ('cache_write_input_tokens',)):return None
    for key in COUNTERS + ('cache_write_input_tokens',):
        default = 0 if key == 'cache_write_input_tokens' else None
        value = current.get(key, default)
        before = previous.get(key, default) if previous is not None else 0
        if type(value) is not int or type(before) is not int:return None
        if value < before and not reset:return None
        delta = value if value < before else value-before
        if delta != step.get(key, default):return None
    return estimate_usd(model, step)


def sum_costs(rows):
    """Combine (tokens, USD) pairs without hiding an unpriced positive contribution."""
    rows = list(rows)
    if any(tokens > 0 and cost is None for tokens, cost in rows):return None
    known = [cost for _, cost in rows if cost is not None]
    return sum(known) if known else None
