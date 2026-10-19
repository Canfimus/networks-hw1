"""Checks of the experiment pipeline and statistics helpers."""

import itertools
import math
import random
import unittest

from bfs import shortest_path_length
from experiment import edge_isolation_probability, run_trials, summarize
from failures import fail_random_links
from generate import default_host_pair
from stats_utils import mean_with_ci, prob_all_of_m_links_failed, wilson_interval
from topology import build_fat_tree


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
        tree, n_elig, n_failed, _, dist = self.result
        rows = summarize(self.k, self.percents, n_failed, n_elig, dist)
        for row, p in zip(rows, self.percents):
            conn = [d for d in dist[p] if d is not None]
            self.assertEqual(row["connected"], len(conn))
            self.assertAlmostEqual(row["p_connected"], len(conn) / 60)
            if conn:
                self.assertAlmostEqual(row["mean_len"], sum(conn) / len(conn))
            else:
                self.assertTrue(math.isnan(row["mean_len"]))
            self.assertEqual(sum(row["length_counts"].values()), len(conn))
            self.assertLessEqual(row["p_connected_lo95"], row["p_connected"])
            self.assertGreaterEqual(row["p_connected_hi95"], row["p_connected"])


class TestStats(unittest.TestCase):
    def test_wilson(self):
        lo, hi = wilson_interval(50, 100)
        self.assertAlmostEqual(lo, 0.4038, places=3)
        self.assertAlmostEqual(hi, 0.5962, places=3)
        lo, hi = wilson_interval(0, 500)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.00762, places=4)
        lo, hi = wilson_interval(500, 500)
        self.assertAlmostEqual(lo, 1 - 0.00762, places=4)
        self.assertEqual(hi, 1.0)

    def test_mean_ci(self):
        m, s, ci = mean_with_ci([6, 6, 8, 8])
        self.assertEqual(m, 7)
        self.assertAlmostEqual(s, math.sqrt(4 / 3))
        self.assertAlmostEqual(ci, 1.959964 * math.sqrt(4 / 3) / 2, places=5)
        self.assertTrue(math.isnan(mean_with_ci([6])[2]))
        self.assertTrue(math.isnan(mean_with_ci([])[0]))

    def test_hypergeometric_against_enumeration(self):
        n_elig, n_fail, m = 8, 4, 2
        subsets = list(itertools.combinations(range(n_elig), n_fail))
        hit = sum(1 for s in subsets if set(range(m)) <= set(s))
        self.assertAlmostEqual(prob_all_of_m_links_failed(m, n_fail, n_elig), hit / len(subsets))
        self.assertEqual(prob_all_of_m_links_failed(5, 4, 8), 0.0)

    def test_edge_isolation_against_enumeration_k2(self):
        """k = 2: 4 eligible links; each edge switch has a single uplink."""
        for n in range(5):
            subsets = list(itertools.combinations(range(4), n))
            # links 0 and 1 stand for the two different edge switches' uplinks
            hit = sum(1 for s in subsets if 0 in s or 1 in s)
            self.assertAlmostEqual(edge_isolation_probability(2, n, 4), hit / len(subsets))


if __name__ == "__main__":
    unittest.main()
