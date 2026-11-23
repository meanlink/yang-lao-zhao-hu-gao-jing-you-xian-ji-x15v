import csv
import hashlib
import io
import math
from collections import Counter
from pathlib import Path

from .schemas import FEATURES

CORPUS = Path(__file__).resolve().parents[1] / 'scripts' / 'synthetic_shift_labels.csv'


class PriorityModel:
    """Laplace-smoothed Bernoulli naive Bayes over four binary workflow signals."""

    def __init__(self, corpus=CORPUS):
        raw = corpus.read_bytes()
        self.checksum = hashlib.sha256(raw).hexdigest()
        rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
        counts = Counter(int(row['priority']) for row in rows)
        if set(counts) != {1, 2, 3} or any(row[key] not in ('0', '1') for row in rows for key in FEATURES):
            raise ValueError('Training corpus requires all three priorities and binary signals')
        self.priors = {level: (count + 1) / (len(rows) + 3) for level, count in counts.items()}
        self.present = {
            level: {key: (1 + sum(int(row[key]) for row in rows if int(row['priority']) == level)) / (count + 2)
                    for key in FEATURES}
            for level, count in counts.items()
        }
        self.description = {'kind': 'Bernoulli NB', 'checksum': self.checksum,
                            'training_rows': len(rows), 'class_sizes': dict(counts), 'alpha': 1}

    def score(self, signals):
        if any(type(signals[key]) is not bool for key in FEATURES):
            raise ValueError('Incomplete signals cannot be classified')
        evidence = {
            level: {key: math.log(prob if signals[key] else 1 - prob) for key, prob in values.items()}
            for level, values in self.present.items()
        }
        totals = {level: math.log(self.priors[level]) + sum(items.values()) for level, items in evidence.items()}
        winner, runner, *_ = sorted(totals, key=lambda level: (totals[level], level), reverse=True)
        weights = {level: math.exp(score - totals[winner]) for level, score in totals.items()}
        normalizer = sum(weights.values())
        return {
            'candidate': winner, 'runner_up': runner,
            'probabilities': {level: value / normalizer for level, value in weights.items()},
            'contributions': [{'feature': key, 'value': signals[key],
                               'log_odds': evidence[winner][key] - evidence[runner][key]} for key in FEATURES],
            'prior_log_odds': math.log(self.priors[winner] / self.priors[runner]),
            'model_checksum': self.checksum,
        }
