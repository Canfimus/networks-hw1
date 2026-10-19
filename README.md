# HW1 – Fat-Tree Topology Generation and Failure Analysis

Course 361.2.2460 – Communication networks for data centers and AI, Semester A 2026/27.

This project builds the k-ary fat-tree from Al-Fares et al. [1], randomly fails
switch-to-switch links, and answers the question:

**How does the average shortest path length between two hosts in different pods change as
the fraction of failed inter-switch links increases?**

The graph, the failure model and BFS are written in plain Python, with no graph library.
`matplotlib` is used only for the plots.

## 1. The fat-tree topology

A k-ary fat-tree (k even) uses identical k-port switches in three tiers (paper, Section 2.2
and Figure 3):

| Element | Formula | k = 4 | k = 8 |
|---|---|---|---|
| Pods | k | 4 | 8 |
| Edge / aggregation switches per pod | k/2 each | 2 | 4 |
| Core switches | (k/2)² | 4 | 16 |
| Hosts | k³/4 | 16 | 128 |
| Switch-to-switch links | k³/2 | 32 | 256 |

The tiers are wired as follows:

* **Host – Edge:** each edge switch connects to k/2 hosts.
* **Edge – Aggregation:** each edge switch connects to every aggregation switch in its pod.
* **Aggregation – Core:** the cores form k/2 rows of k/2. Aggregation switch `a` of every
  pod connects to all cores in row `a`. So each core has exactly one link to each pod,
  as in the paper's Figure 3.

In the intact network every switch has exactly k neighbours. Two hosts are 2 hops apart
if they share an edge switch, 4 hops apart if they are in the same pod, and 6 hops apart
if they are in different pods.

## 2. Implementation

| File | Contents |
|---|---|
| [topology.py](topology.py) | `build_fat_tree(k)` builds the graph |
| [failures.py](failures.py) | Random link failures (`fail_random_links`) |
| [bfs.py](bfs.py) | Our BFS: `shortest_path_length(adj, src, dst)` returns `None` if there is no path |
| [generate.py](generate.py) | CLI: build one topology, optionally fail links, print a report |
| [experiment.py](experiment.py) | CLI: runs the experiment and saves results and plots |
| [plot_results.py](plot_results.py) | Draws the plots from `results/*/summary.csv` |
| [tests/](tests/) | Correctness tests (`unittest`) |

* **Graph:** an adjacency list, `dict[node, set[node]]`. Nodes are tuples such as
  `("edge", pod, e)` or `("core", row, col)`.
* **BFS:** a standard queue-based BFS. Every link counts as one hop, so the first time BFS
  reaches the destination it has found the shortest path. If the queue empties first, the
  hosts are disconnected.

## 3. How to run

Requirements: Python ≥ 3.8 and matplotlib (tested with Python 3.13.7, matplotlib 3.10.8).

```bash
pip install -r requirements.txt

# One topology, with optional failures
python generate.py --k 4
python generate.py --k 8 --failure-percent 30 --seed 1 --show-failed

# Main experiment (k=8, 500 trials per rate) -> results/main/
python experiment.py --outdir results/main

# Larger run (10,000 trials, finer grid at high failure rates) -> results/zoom/
python experiment.py --trials 10000 --percents 0 10 20 30 40 50 55 60 65 70 72.5 75 77.5 80 82.5 85 87.5 90 --outdir results/zoom

# Tests
python -m unittest discover -s tests
```

`python generate.py --k 8 --failure-percent 30 --seed 1` prints (shortened):

```
k = 8 fat-tree
  host  nodes :    128   (expected 128)
  ...
  switch degrees (intact): [8]
Failures: requested rate 0.3, seed 1
  failed links: 77  (= 30.08% of eligible)
  hosts reachable from 10.0.0.2: 128 / 128
Shortest path 10.0.0.2 -> 10.7.3.5: 6 hops
```

## 4. Parameters

**`generate.py`**

| Parameter | Default | Meaning |
|---|---|---|
| `--k` | 4 | Switch port count (even integer ≥ 2) |
| `--failure-rate` / `--failure-percent` | 0 | Fraction [0, 1] or percentage [0, 100] of switch-to-switch links to fail (use only one of them) |
| `--seed` | 0 | Random seed for the failures |
| `--src`, `--dst` | first host of pod 0, last host of pod k−1 | Hosts in the paper's format `10.pod.edge.id` |
| `--edges-out PATH` | – | Write the surviving links to a file |
| `--show-failed` | off | Print the failed links |

**`experiment.py`**

| Parameter | Default | Meaning |
|---|---|---|
| `--k` | 8 | Switch port count |
| `--trials` | 500 | Random trials per failure rate |
| `--percents` | `0 1 2 5 10 15 20 25 30 40 50 60 70 80 90` | Failure percentages to test |
| `--seed` | 2026 | Master random seed |
| `--src`, `--dst` | `10.0.0.2`, `10.7.3.5` (for k = 8) | Must be in different pods |
| `--outdir` | `results` | Output folder |
| `--no-plot` | off | Skip the plots |

Invalid input, such as an odd k, a rate outside [0, 1] or an unknown host, is rejected with
an error message.

## 5. Failure model

* Only **switch-to-switch links** can fail (edge–agg and agg–core, 256 links for k = 8).
  Host links never fail, since each host has only one link.
* For a failure rate f, exactly **n = round(f × 256)** distinct links fail, chosen uniformly
  at random. The plots show the actual percentage. For example, 10% becomes 26 links,
  which is 10.16%.
* Nodes are never removed, and a fixed seed always gives the same failures.
* In each trial the links are shuffled once, and failure rate f fails the first n links.
  So within one trial, the links that are down at 20% include those down at 10%.

## 6. Experiment

* **Setup:** k = 8 fat-tree (128 hosts, 80 switches). The two fixed hosts are `10.0.0.2`
  (pod 0) and `10.7.3.5` (pod 7). Because of the fat-tree's symmetry, any pair of hosts in
  different pods behaves the same.
* **Parameters:** failure rates from 0% to 90%, 500 random trials per rate, seed 2026.
* **Each trial:** copy the intact graph, remove the failed links, run BFS between the two
  hosts, and record the path length or "disconnected".
* **Metrics:**
  * **connectivity probability** = connected trials / all trials;
  * **average shortest path length** over the *connected trials only*. Disconnected trials
    have no path, so they are not counted as some arbitrary distance.

We measure hop counts in the physical graph. This is not latency, and it is not the path
the paper's routing algorithm would pick.

## 7. Results

Main run (`results/main/log.txt`, 500 trials per rate):

| Failed links | 0% | 10.2% | 19.9% | 30.1% | 39.8% | 50.0% | 60.2% | 69.9% | 80.1% | 89.8% |
|---|---|---|---|---|---|---|---|---|---|---|
| Connected trials | 500 | 500 | 497 | 487 | 473 | 451 | 371 | 230 | 30 | 0 |
| Connectivity probability | 1.000 | 1.000 | 0.994 | 0.974 | 0.946 | 0.902 | 0.742 | 0.460 | 0.060 | 0.000 |
| Average path length | 6.000 | 6.008 | 6.036 | 6.152 | 6.381 | 6.984 | 7.849 | 9.591 | 8.800 | – |

### 7.1 Connectivity probability

![Connectivity probability](results/main/connectivity_probability.png)

* The fat-tree is very robust. With up to 10% of switch links failed, the hosts stayed
  connected in every trial. At 30% they were still connected in 97% of trials.
* Beyond about 60% connectivity collapses: 6% of trials are connected at 80%, and none
  at 90%.
* The weak point is the **edge switch**. A host depends on a single edge switch with only
  k/2 = 4 uplinks. If those 4 links fail, the host is cut off, no matter how much
  redundancy exists in the 16 core switches above it.

### 7.2 Average shortest path length

![Average path length](results/main/avg_path_length.png)

The colour of each dot is the connectivity probability, i.e. the share of trials that the
average is based on. Dark dots average over almost all trials, and yellow dots over only a
few.

* Up to 20% failures the average stays at about 6 hops. Between two pods there are
  (k/2)² = 16 different 6-hop paths, one through each core switch, and usually at least
  one survives.
* When all 6-hop paths are broken, the path has to detour (down to another edge switch
  and back up). Each detour adds 2 hops, so the average grows: 6.15 at 30%, 6.98 at 50%,
  9.59 at 70%.
* **Surprising result: at very high failure rates the average goes back *down*** (9.59 at
  70% → 8.80 at 80%). Only 30 trials are connected at 80%, so we confirmed this with
  10,000 trials per rate (`results/zoom/log.txt`):

  ![Average path length, 10,000 trials](results/zoom/avg_path_length.png)

  | Failed links | 60% | 70% | 75% | 80% | 85% | 90% |
  |---|---|---|---|---|---|---|
  | Connected trials (of 10,000) | 7289 | 4505 | 2248 | 621 | 122 | 15 |
  | Average path length | 7.81 | 9.43 | 9.91 | 8.91 | 6.93 | 6.27 |

**Why? Survivorship bias.** The average includes only the trials that are still connected.
A long detour needs many links to survive, a short path only a few. When 85–90% of the
links are down, long detours almost never survive. So the few trials that are still
connected are mostly those where a *short* path happened to survive. More failures never
shorten the path within a single trial. The average drops only because trials with long
paths become disconnected and leave the average.

This is why the colour matters: at 90%, "6.3 hops" describes only 15 of 10,000 trials.

## 8. Conclusions and limitations

* The fat-tree's many parallel paths make it highly tolerant of random link failures. Up
  to about 20% failed links, connectivity and path length barely change.
* Under heavier failures paths first get longer, and then the hosts become disconnected.
  The edge switch, with only k/2 uplinks, is the main weak point. A larger k means more
  uplinks and more resilience.
* **Limitations:**
  * we measure hop count in the physical graph, not latency, bandwidth, or the routes the
    paper's routing scheme would actually choose (it may not use every detour BFS finds);
  * we test only one k, one host pair, and independent random link failures, with no
    switch failures and no correlated failures.

## 9. AI assistance disclosure

This project was developed with the help of **Claude (Anthropic, Claude Opus 5.5), used
through Claude Code**. The AI read the assignment and the paper, wrote the code, tests
and README, ran the tests and experiments, and helped investigate the unexpected drop in
the average path length. All numbers in this README come from the actual program output
in `results/`. I reviewed the code and results and take responsibility for the submission.

## Reference

[1] M. Al-Fares, A. Loukissas, and A. Vahdat, "A scalable, commodity data center network
architecture," *SIGCOMM Comput. Commun. Rev.*, vol. 38, no. 4, pp. 63–74, Oct. 2008,
doi: 10.1145/1402946.1402967.
