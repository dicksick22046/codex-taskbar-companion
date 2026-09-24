import unittest
from scripts.check_model_prices import HEADER, standard_prices, differences


def row(name, short, long):
    return '| ' + ' | '.join((name, *short, *long)) + ' |'


SHORT = {
    'gpt-6-astra': ('$10', '$1', '$12.50', '$50'),
    'gpt-6-sol': ('$2', '$0.20', '$2.50', '$10'),
    'gpt-6-luna': ('$0.10', '$0.01', '$0.125', '$0.50'),
    'gpt-5.6-sol': ('$4', '$0.40', '$5', '$20'),
    'gpt-5.6-terra': ('$2', '$0.20', '$2.50', '$12'),
    'gpt-5.6-luna': ('$0.20', '$0.02', '$0.25', '$1.20'),
    'gpt-5.5 (<272K context length)': ('$5', '$0.50', '-', '$30'),
    'gpt-5.4 (<272K context length)': ('$2.50', '$0.25', '-', '$15'),
    'gpt-5.4-mini': ('$0.75', '$0.075', '-', '$4.50'),
}
LONG = {
    'gpt-6-astra': ('$20', '$2', '$25', '$75'),
    'gpt-6-sol': ('$4', '$0.40', '$5', '$15'),
    'gpt-6-luna': ('$0.20', '$0.02', '$0.25', '$0.75'),
    'gpt-5.6-sol': ('$8', '$0.80', '$10', '$30'),
    'gpt-5.6-terra': ('$4', '$0.40', '$5', '$18'),
    'gpt-5.6-luna': ('$0.40', '$0.04', '$0.50', '$1.80'),
    'gpt-5.5 (<272K context length)': ('$10', '$1', '-', '$45'),
    'gpt-5.4 (<272K context length)': ('$5', '$0.50', '-', '$22.50'),
    'gpt-5.4-mini': ('-', '-', '-', '-'),
}


def page(extra=()):
    lines = ['### Standard pricing data',
             '| ' + ' | '.join(HEADER) + ' |',
             '| ' + ' | '.join('---' for _ in HEADER) + ' |']
    lines.extend(row(name, short, LONG[name]) for name, short in SHORT.items())
    lines.extend(extra)
    lines.extend(['', '### Batch pricing data', row('gpt-6-sol', ('$1', '$0.10', '$1.25', '$5'),
                                                    ('$2', '$0.20', '$2.50', '$7.50'))])
    return '\n'.join(lines)


class OfficialPriceAuditTests(unittest.TestCase):
    def test_only_standard_rates_are_used_and_current_reviewed_rows_match(self):
        rows = standard_prices(page())
        self.assertEqual(rows['gpt-6-sol'][0], 2)
        self.assertEqual(rows['gpt-6-sol'][7], 15)
        self.assertIn('gpt-5.5', rows)
        self.assertEqual(differences(rows, set(rows)), [])

    def test_new_model_and_changed_rate_require_review(self):
        rows = standard_prices(page(extra=[row('gpt-7-new', ('$1', '$0.10', '$1.25', '$5'),
                                                   ('$2', '$0.20', '$2.50', '$7.50'))]))
        rows['gpt-6-sol'] = (rows['gpt-6-sol'][0] + 1, *rows['gpt-6-sol'][1:])
        problems = differences(rows, set(rows)-{'gpt-7-new'})
        self.assertTrue(any('New Standard model' in item for item in problems))
        self.assertTrue(any('rates changed for gpt-6-sol' in item for item in problems))

    def test_missing_or_changed_standard_section_fails_closed(self):
        for markdown in (page().replace('### Standard pricing data', '### Fast pricing data'),
                         page().replace('Short context cache writes', 'Cache write guess'),
                         page().replace('$2.50', 'unknown', 1)):
            with self.subTest(markdown=markdown[:70]),self.assertRaises(ValueError):
                standard_prices(markdown)


if __name__ == '__main__':
    unittest.main()
