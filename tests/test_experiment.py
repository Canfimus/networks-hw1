"""Checks of the experiment pipeline."""

import math
import random
import unittest

from bfs import shortest_path_length
from experiment import run_trials, summarize
from failures import fail_random_links
from generate import default_host_pair


class TestExperiment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.k = 4
        cls.percents = [0, 10, 25, 50, 75, 100]
        cls.src, cls.dst = default_host_pair(cls.k)
        cls.result = run_trials(cls.k, cls.percents, 60, 11, cls.src, cls.dst)

    def test_zero_failures_baseline(self):
        _, _, n_failed, _, dist = self.result
        self.assertEqual(n_failed[0], 0)
        self.assertEqual(dist[0], [6] * 60)

    def test_full_failure_disconnects(self):
        _, _, _, _, dist = self.result
        self.assertEqual(dist[100], [None] * 60)

    def test_reproducible(self):
        again = run_trials(self.k, self.percents, 60, 11, self.src, self.dst)
        self.assertEqual(again[4], self.result[4])
        other = run_trials(self.k, self.percents, 60, 12, self.src, self.dst)
        self.assertNotEqual(other[4], self.result[4])

    def test_nested_failures_are_monotone(self):
        """Within one trial, more failures never shorten the path or reconnect."""
        _, _, _, _, dist = self.result
        for t in range(60):
            seq = [dist[p][t] for p in self.percents]
            for a, b in zip(seq, seq[1:]):
                if a is None:
                    self.assertIsNone(b)
                elif b is not None:
                    self.assertGreaterEqual(b, a)
            self.assertTrue(all(d is None or (d >= 6 and d % 2 == 0) for d in seq))

    def test_trial_reproducible_by_generate(self):
        """generate.py's failure draw with a trial seed equals that trial."""
        tree, _, _, seeds, dist = self.result
        for t in range(5):
            adj, _ = fail_random_links(tree, 0.5, random.Random(seeds[t]))
            self.assertEqual(shortest_path_length(adj, self.src, self.dst), dist[50][t])

    def test_summary(self):
        _, n_elig, n_failed, _, dist = self.result
        rows = summarize(self.percents, n_failed, n_elig, dist)
        for row, p in zip(rows, self.percents):
            conn = [d for d in dist[p] if d is not None]
            self.assertEqual(row["connected"], len(conn))
            self.assertAlmostEqual(row["p_connected"], len(conn) / 60)
            if conn:
                self.assertAlmostEqual(row["mean_len"], sum(conn) / len(conn))
            else:
                self.assertTrue(math.isnan(row["mean_len"]))


if __name__ == "__main__":
    unittest.main()
