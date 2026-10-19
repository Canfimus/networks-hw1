"""Checks of the failure model and of BFS."""

import random
import unittest

from bfs import bfs_distances, shortest_path_length
from failures import (eligible_links, fail_random_links, num_links_to_fail,
                      random_failure_order, remove_links)
from topology import AGG, CORE, EDGE, HOST, build_fat_tree, is_switch_link, link_kind


class TestBFS(unittest.TestCase):
    def test_path_graph(self):
        adj = {0: {1}, 1: {0, 2}, 2: {1, 3}, 3: {2}}
        self.assertEqual(shortest_path_length(adj, 0, 3), 3)
        self.assertEqual(shortest_path_length(adj, 2, 2), 0)
        self.assertEqual(bfs_distances(adj, 0), {0: 0, 1: 1, 2: 2, 3: 3})

    def test_shortest_of_several_routes(self):
        # cycle 0-1-2-3-4-5-0: distance 0 -> 4 is 2 (the short way round)
        adj = {i: {(i - 1) % 6, (i + 1) % 6} for i in range(6)}
        self.assertEqual(shortest_path_length(adj, 0, 4), 2)
        self.assertEqual(shortest_path_length(adj, 0, 3), 3)

    def test_disconnected(self):
        adj = {0: {1}, 1: {0}, 2: {3}, 3: {2}, 4: set()}
        self.assertIsNone(shortest_path_length(adj, 0, 3))
        self.assertIsNone(shortest_path_length(adj, 0, 4))
        self.assertEqual(set(bfs_distances(adj, 0)), {0, 1})

    def test_agrees_with_brute_force_on_random_graphs(self):
        rng = random.Random(1)
        for _ in range(200):
            n = rng.randint(2, 9)
            adj = {i: set() for i in range(n)}
            for u in range(n):
                for v in range(u + 1, n):
                    if rng.random() < 0.3:
                        adj[u].add(v)
                        adj[v].add(u)
            # Bellman-Ford style relaxation as an independent reference
            ref = {i: float("inf") for i in range(n)}
            ref[0] = 0
            for _ in range(n):
                for u in range(n):
                    for v in adj[u]:
                        ref[v] = min(ref[v], ref[u] + 1)
            for t in range(n):
                d = shortest_path_length(adj, 0, t)
                self.assertEqual(d, None if ref[t] == float("inf") else ref[t])


class TestFailureCount(unittest.TestCase):
    def test_rounding(self):
        self.assertEqual(num_links_to_fail(0.0, 256), 0)
        self.assertEqual(num_links_to_fail(0.01, 256), 3)    # 2.56 -> 3
        self.assertEqual(num_links_to_fail(0.10, 256), 26)   # 25.6 -> 26
        self.assertEqual(num_links_to_fail(0.25, 256), 64)   # exact
        self.assertEqual(num_links_to_fail(0.5, 3), 2)       # 1.5 -> 2 (ties up)
        self.assertEqual(num_links_to_fail(0.1, 5), 1)       # 0.5 -> 1 (ties up)
        self.assertEqual(num_links_to_fail(1.0, 256), 256)

    def test_invalid_rates(self):
        for bad in (-0.1, 1.01, 50):
            with self.assertRaises(ValueError):
                num_links_to_fail(bad, 10)
        with self.assertRaises(TypeError):
            num_links_to_fail("0.1", 10)


class TestFailures(unittest.TestCase):
    def setUp(self):
        self.tree = build_fat_tree(8)
        self.elig = eligible_links(self.tree)

    def test_eligible_links_are_switch_links(self):
        self.assertEqual(len(self.elig), 8 ** 3 // 2)
        self.assertTrue(all(link_kind(l) in ("edge-agg", "agg-core") for l in self.elig))
        hosts_links = [l for l in self.tree.links if not is_switch_link(l)]
        self.assertTrue(all(link_kind(l) == "host-edge" for l in hosts_links))

    def test_zero_failures_is_baseline(self):
        adj, failed = fail_random_links(self.tree, 0.0, random.Random(0))
        self.assertEqual(failed, [])
        self.assertEqual(adj, self.tree.adj)
        self.assertEqual(shortest_path_length(adj, (HOST, 0, 0, 0), (HOST, 7, 3, 3)), 6)

    def test_failed_links_removed(self):
        adj, failed = fail_random_links(self.tree, 0.3, random.Random(5))
        self.assertEqual(len(failed), num_links_to_fail(0.3, len(self.elig)))
        self.assertEqual(len({frozenset(l) for l in failed}), len(failed), "no repeats")
        failed_set = set(failed)
        for u, v in failed:
            self.assertTrue(is_switch_link((u, v)))
            self.assertNotIn(v, adj[u])
            self.assertNotIn(u, adj[v])
        for u, v in self.tree.links:
            if (u, v) not in failed_set:
                self.assertIn(v, adj[u])
        remaining = sum(len(nb) for nb in adj.values()) // 2
        self.assertEqual(remaining, len(self.tree.links) - len(failed))

    def test_nodes_preserved_and_original_untouched(self):
        before = {n: set(nb) for n, nb in self.tree.adj.items()}
        adj, _ = fail_random_links(self.tree, 1.0, random.Random(0))
        self.assertEqual(set(adj), set(self.tree.adj))
        self.assertEqual(self.tree.adj, before)
        # all switch links gone, host links all kept
        for node, nbrs in adj.items():
            if node[0] in (AGG, CORE):
                self.assertEqual(nbrs, set())
            if node[0] == EDGE:
                self.assertTrue(all(n[0] == HOST for n in nbrs))
                self.assertEqual(len(nbrs), 4)

    def test_reproducible_with_seed(self):
        a = fail_random_links(self.tree, 0.2, random.Random(42))
        b = fail_random_links(self.tree, 0.2, random.Random(42))
        c = fail_random_links(self.tree, 0.2, random.Random(43))
        self.assertEqual(a, b)
        self.assertNotEqual(a[1], c[1])
        # also reproducible across fresh topology objects
        d = fail_random_links(build_fat_tree(8), 0.2, random.Random(42))
        self.assertEqual(a[1], d[1])

    def test_uniform_selection(self):
        """Every eligible link fails with frequency close to n/N."""
        tree = build_fat_tree(4)
        elig = eligible_links(tree)
        n, trials = 8, 8000
        freq = {l: 0 for l in elig}
        rng = random.Random(3)
        for _ in range(trials):
            for l in random_failure_order(elig, rng)[:n]:
                freq[l] += 1
        p = n / len(elig)                           # 0.25
        sd = (p * (1 - p) / trials) ** 0.5          # ~0.0048
        for l, c in freq.items():
            self.assertLess(abs(c / trials - p), 5 * sd, l)


class TestDisconnection(unittest.TestCase):
    def test_full_failure_disconnects_except_same_edge(self):
        tree = build_fat_tree(4)
        adj, _ = fail_random_links(tree, 1.0, random.Random(0))
        self.assertEqual(shortest_path_length(adj, (HOST, 0, 0, 0), (HOST, 0, 0, 1)), 2)
        self.assertIsNone(shortest_path_length(adj, (HOST, 0, 0, 0), (HOST, 0, 1, 0)))
        self.assertIsNone(shortest_path_length(adj, (HOST, 0, 0, 0), (HOST, 3, 1, 1)))

    def test_cut_edge_uplinks(self):
        tree = build_fat_tree(4)
        cut = [l for l in tree.links if (EDGE, 0, 0) in l and link_kind(l) == "edge-agg"]
        adj = remove_links(tree.adj, cut)
        self.assertIsNone(shortest_path_length(adj, (HOST, 0, 0, 0), (HOST, 2, 0, 0)))
        self.assertIsNone(shortest_path_length(adj, (HOST, 0, 0, 0), (HOST, 0, 1, 0)))
        self.assertEqual(shortest_path_length(adj, (HOST, 0, 0, 0), (HOST, 0, 0, 1)), 2)

    def test_cut_pod_from_core(self):
        tree = build_fat_tree(4)
        cut = [l for l in tree.links if link_kind(l) == "agg-core"
               and any(n[0] == AGG and n[1] == 0 for n in l)]
        adj = remove_links(tree.adj, cut)
        self.assertIsNone(shortest_path_length(adj, (HOST, 0, 0, 0), (HOST, 1, 0, 0)))
        self.assertEqual(shortest_path_length(adj, (HOST, 0, 0, 0), (HOST, 0, 1, 0)), 4)

    def test_detour_through_other_edge_is_8_hops(self):
        """If src's aggregation switches lose their core links except via a
        detour, the path gets longer: agg 0 of pod 0 loses its core links and
        the src edge loses its link to agg 1 -> path must go down and up again."""
        tree = build_fat_tree(4)
        cut = [l for l in tree.links
               if set(l) == {(EDGE, 0, 0), (AGG, 0, 1)}
               or (link_kind(l) == "agg-core" and (AGG, 0, 0) in l)]
        adj = remove_links(tree.adj, cut)
        # h(0,0,0) - e00 - a00 - e01 - a01 - core - agg(pod 1) - edge - host = 8
        self.assertEqual(shortest_path_length(adj, (HOST, 0, 0, 0), (HOST, 1, 0, 0)), 8)


if __name__ == "__main__":
    unittest.main()
