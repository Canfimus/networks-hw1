# HW1 – Fat-Tree Topology Generation and Failure Analysis

Course 361.2.2460 – Communication networks for data centers and AI, Semester A 2026/27.

This project builds the k-ary fat-tree from Al-Fares et al. [1], randomly fails
switch-to-switch links, and measures how the shortest path between two hosts in
different pods changes.

**Research question:** *How does the average shortest path length between two hosts in
different pods change as the fraction of failed inter-switch links increases?*

The graph, the failure model and BFS are written in plain Python, with no graph library.
`matplotlib` is used only for the plots.

## 1. The fat-tree topology

A k-ary fat-tree (k even) is built from identical k-port switches in three tiers
(paper, Section 2.2 and Figure 3):

| Element | Formula | k = 4 | k = 8 |
|---|---|---|---|
| Pods | k | 4 | 8 |
| Edge switches per pod | k/2 | 2 | 4 |
| Aggregation switches per pod | k/2 | 2 | 4 |
| Core switches | (k/2)² | 4 | 16 |
| Hosts | k³/4 | 16 | 128 |
| Switch-to-switch links | k³/2 | 32 | 256 |

The links are created as follows:

* **Host – Edge:** each edge switch connects to k/2 hosts.
* **Edge – Aggregation:** each edge switch connects to every aggregation switch in its pod.
* **Aggregation – Core:** the (k/2)² core switches are arranged in k/2 rows of k/2.
  Aggregation switch number `a` in *every* pod connects to all k/2 cores in row `a`. As
  a result, each core switch has exactly one link to each pod. This matches the paper's
  rule ("the i-th port of any core switch is connected to pod i… on (k/2) strides") and
  the links shown in Figure 3. For k = 4: `10.0.2.1 → 10.4.1.1, 10.4.1.2` and
  `10.0.3.1 → 10.4.2.1, 10.4.2.2`.

In the complete topology every switch has exactly k neighbours. In the intact network:

* hosts on the same edge switch are 2 hops apart;
* hosts in the same pod but on different edge switches are 4 hops apart;
* hosts in different pods are 6 hops apart (host → edge → agg → core → agg → edge → host).

## 2. Project structure

| File | Contents |
|---|---|
| [topology.py](topology.py) | `build_fat_tree(k)`: builds the graph; also the expected counts and the paper's `10.pod.switch.id` names |
| [failures.py](failures.py) | Random link failures: `eligible_links`, `num_links_to_fail`, `fail_random_links` |
| [bfs.py](bfs.py) | Our BFS: `shortest_path_length(adj, src, dst)`, which returns `None` if there is no path |
| [generate.py](generate.py) | CLI: build one topology, optionally fail links, print a report |
| [experiment.py](experiment.py) | CLI: the main experiment; saves CSV results and plots |
| [plot_results.py](plot_results.py) | Draws the two plots from `summary.csv` |
| [tests/](tests/) | Correctness tests (`unittest`) |
| [results/](results/) | Experiment output: `main/` (500 trials) and `zoom/` (10,000 trials) |

**Graph representation:** an adjacency list `adj: dict[node, set[node]]`. Nodes are
tuples such as `("host", pod, edge, h)`, `("edge", pod, e)`, `("agg", pod, a)` and
`("core", row, col)`. The tree also keeps an ordered list of all links, and random
failures are always drawn from this list. Using a fixed order makes runs with the same
seed reproducible.

**BFS:** this is a standard queue-based breadth-first search. All links count as 1 hop,
so BFS visits nodes in order of their distance from the source. The first time it
reaches the destination, it has found the shortest path. If the queue empties first, the
hosts are disconnected and BFS returns `None`.

## 3. Installation

Requirements: Python ≥ 3.8 (tested with 3.13.7) and matplotlib (tested with 3.10.8).

```bash
pip install -r requirements.txt
```

## 4. How to run

```bash
# Generate one topology (optionally with failures)
python generate.py --k 4
python generate.py --k 8 --failure-percent 30 --seed 1
python generate.py --k 8 --failure-rate 0.3 --seed 1 --src 10.0.0.2 --dst 10.5.1.3 --show-failed
python generate.py --k 4 --failure-percent 25 --edges-out topo_k4.txt

# Main experiment: k=8, 500 trials per failure rate (about 1 s) -> results/main/
python experiment.py --outdir results/main

# Larger run: 10,000 trials, finer grid at high failure rates (about 30 s) -> results/zoom/
python experiment.py --trials 10000 --percents 0 10 20 30 40 50 55 60 65 70 72.5 75 77.5 80 82.5 85 87.5 90 --outdir results/zoom

# Run the tests
python -m unittest discover -s tests -v
```

Example output of `python generate.py --k 8 --failure-percent 30 --seed 1`:

```
k = 8 fat-tree
  host  nodes :    128   (expected 128)
  edge  nodes :     32   (expected 32)
  agg   nodes :     32   (expected 32)
  core  nodes :     16   (expected 16)
  host-edge links:    128   (expected 128)
  edge-agg  links:    128   (expected 128)
  agg-core  links:    128   (expected 128)
  switch degrees (intact): [8]

Failures: requested rate 0.3, seed 1
  eligible (switch-switch) links: 256
  failed links: 77  (= 30.08% of eligible)
  failed by kind: {'edge-agg': 35, 'agg-core': 42}
  edge switches with no uplink left: 0
  hosts reachable from 10.0.0.2: 128 / 128

Shortest path 10.0.0.2 -> 10.7.3.5: 6 hops
```

## 5. Parameters

**`generate.py`**

| Parameter | Default | Meaning |
|---|---|---|
| `--k` | 4 | Switch port count; must be an even integer ≥ 2 |
| `--failure-rate` | 0 | Fraction of switch-to-switch links to fail, in [0, 1] |
| `--failure-percent` | – | The same value as a percentage in [0, 100]. Use either this or `--failure-rate`, not both |
| `--seed` | 0 | Random seed for the failures |
| `--src`, `--dst` | `10.0.0.2`, last host of the last pod | Hosts in the paper's format `10.pod.edge.id`, where id ∈ [2, k/2+1] |
| `--edges-out PATH` | – | Write the surviving links to a file |
| `--show-failed` | off | Print every failed link |

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

Invalid values are rejected with an error message. Examples: odd k, a rate outside
[0, 1], or a host address that doesn't exist for the given k.

## 6. Failure model

* Only **switch-to-switch links** can fail (edge–agg and agg–core): 256 links for k = 8.
  Host–edge links never fail, because each host has only one link.
* For a failure rate f, exactly **n = round(f × 256)** links fail (ties round up), chosen
  uniformly at random without replacement. The plots use the *actual* percentage n/256.
  For example, 10% becomes 26 links, which is 10.16%.
* Nodes are never removed. A switch whose links all failed simply has no neighbours.
* **Implementation detail:** each trial shuffles the 256 links once. A failure rate f
  then fails the first n links of that shuffled list. So, within one trial, the links
  down at 20% include those down at 10%. Different trials use different random seeds,
  and every trial seed is saved in `trials.csv`.
* **Limitations:** failures are independent and random. The model does not include
  switch failures, correlated failures (e.g. a whole line card), or links that are only
  partly degraded.

## 7. Experiment

* k = 8 fat-tree (128 hosts, 80 switches).
* Fixed hosts: `10.0.0.2` (pod 0) → `10.7.3.5` (pod 7). By the symmetry of the fat-tree,
  any two hosts in different pods behave the same.
* Failure rates from 0% to 90%, with 500 random trials per rate and seed 2026.
* Each trial copies the intact graph, removes the failed links, runs BFS between the two
  hosts, and records the path length or "disconnected".

Two metrics are computed for each failure rate:

* **Connectivity probability** = connected trials / total trials.
* **Average shortest path length** = the mean path length over the *connected trials
  only*. Disconnected trials have no path, so they are excluded instead of being given
  an arbitrary distance. The standard deviation is also reported in the tables.

We measure hop counts in the **physical graph**. This is not packet latency, and it is
not the path that the paper's routing algorithm would choose. It is the shortest path
that exists in the cabling after the failures.

## 8. Results

Results of the main run (`results/main/log.txt`, 500 trials per rate):

| Failed links | Connected trials | Connectivity probability | Average path length | Std |
|---|---|---|---|---|
| 0% | 500/500 | 1.000 | 6.000 | 0.00 |
| 5.1% | 500/500 | 1.000 | 6.000 | 0.00 |
| 10.2% | 500/500 | 1.000 | 6.008 | 0.13 |
| 19.9% | 497/500 | 0.994 | 6.036 | 0.27 |
| 30.1% | 487/500 | 0.974 | 6.152 | 0.53 |
| 39.8% | 473/500 | 0.946 | 6.381 | 0.83 |
| 50.0% | 451/500 | 0.902 | 6.984 | 1.27 |
| 60.2% | 371/500 | 0.742 | 7.849 | 1.74 |
| 69.9% | 230/500 | 0.460 | 9.591 | 3.08 |
| 80.1% | 30/500 | 0.060 | 8.800 | 2.76 |
| 89.8% | 0/500 | 0.000 | – | – |

### Connectivity probability

![Connectivity probability](results/main/connectivity_probability.png)

* The fat-tree is very robust. With up to 10% of switch links failed, the two hosts
  stayed connected in all 500 trials. At 30%, they were still connected in 97% of trials.
* Connectivity drops quickly beyond about 60%. At 80% only 6% of trials are connected,
  and at 90% none are.
* The weakest point is the **edge switch**. Each host hangs on a single edge switch, and
  that switch has only k/2 = 4 uplinks. If all 4 fail, the host is cut off, no matter how
  much redundancy exists higher up. The core layer has many more alternatives (16 core
  switches).

### Average shortest path length

![Average path length](results/main/avg_path_length.png)

The colour of each dot shows the connectivity probability at that failure rate, i.e. the
share of trials that the average is based on. Dark dots are averages over almost all
trials. Yellow dots are averages over only a few connected trials. Points with fewer
than 30 connected trials are also labelled "unreliable".

* Up to 20% failures, the average stays almost exactly 6. Between two pods there are
  (k/2)² = 16 different 6-hop paths (one through each core switch), and usually at least
  one of them survives.
* When all 6-hop paths are broken, the shortest path has to take a detour. For example,
  it goes down to another edge switch in the pod and back up again. Each detour adds
  2 hops, so the lengths are 6, 8, 10, …. The average therefore grows: 6.15 at 30%,
  6.98 at 50%, 9.59 at 70%.
* **Surprising result: at very high failure rates the average goes back *down*.** In the
  500-trial run it falls from 9.59 (70%) to 8.80 (80%). Because only 30 trials are
  connected at 80%, we repeated the experiment with 10,000 trials per rate to make sure
  this is real (`results/zoom/log.txt`):

  ![Average path length, 10,000 trials](results/zoom/avg_path_length.png)

  | Failed links | 60% | 70% | 75% | 80% | 85% | 90% |
  |---|---|---|---|---|---|---|
  | Connected trials (of 10,000) | 7289 | 4505 | 2248 | 621 | 122 | 15 |
  | Average path length | 7.81 | 9.43 | 9.91 | 8.91 | 6.93 | 6.27 |

  The peak is about 9.9 hops at 73–75%, after which the average drops back towards 6.

**Why does this happen? Survivorship bias.** The average only includes the trials that
are still connected. A long path needs *many* links to survive, while a short path needs
only a few. When 85–90% of the links are down, it is very unlikely that all the links of
a long detour survived. So in almost every trial that is still connected, the hosts are
connected because a *short* path happened to survive. The network did not get better.
We are averaging over a small group of "lucky" trials, and that group mostly contains
short paths. More failures never make the path shorter within one trial (this is
checked by a test). The average falls only because the long-path trials become
disconnected and drop out of the average.

This is why the average path length must always be read together with the connectivity
probability. At 90%, "average 6.3 hops" describes only 15 out of 10,000 trials.

## 9. Conclusions

* The fat-tree's many parallel paths make it highly tolerant of random link failures.
  Up to about 20% failed switch links, connectivity and path length barely change.
* Under heavier failures, paths first get longer (detours), then the hosts start to get
  disconnected.
* The edge switch, with only k/2 uplinks per host, is the main weak point. A larger k
  gives more uplinks and therefore more resilience.
* These results describe the physical topology only. The actual routing scheme in the
  paper might not use every detour path that BFS finds, so real performance under
  failures could be worse.

## 10. Tests

`python -m unittest discover -s tests -v` → **Ran 34 tests, OK**.

* **Topology** ([tests/test_topology.py](tests/test_topology.py)), for k = 2, 4, 6, 8, 10, 16:
  * node, pod and link counts match the formulas;
  * every switch has degree k;
  * there are no duplicate links;
  * edge–agg and agg–core wiring is correct, and the links of Figure 3 are present;
  * the intact graph is connected;
  * hosts are 2 / 4 / 6 hops apart (same edge / same pod / different pods);
  * there are 16 shortest paths between pods for k = 8.
* **Failures and BFS** ([tests/test_failures_bfs.py](tests/test_failures_bfs.py)):
  * BFS is correct on small hand-made graphs and on random graphs (compared to a simple
    reference algorithm);
  * BFS returns `None` for disconnected hosts;
  * rounding works, and invalid rates are rejected;
  * only switch links fail, and failed links are actually removed;
  * nodes are kept, and 0% failures give the original graph (distance 6);
  * the same seed gives the same result;
  * cutting an edge switch's uplinks disconnects its hosts;
  * a specific failure pattern forces an 8-hop detour.
* **Experiment** ([tests/test_experiment.py](tests/test_experiment.py)):
  * 0% gives 6 hops in every trial, and 100% gives disconnected in every trial;
  * results are reproducible;
  * more failures never shorten the path within a trial;
  * a trial can be reproduced with `generate.py` and its seed;
  * the summary averages are computed correctly.

## 11. Limitations and possible extensions

* We measure hop count in the physical graph, not latency, bandwidth or the actual
  routing behaviour of the paper.
* Only one host pair, one k (8) and random independent link failures are tested.
* Possible extensions: switch failures, failures of host links, comparing several values
  of k, or restricting paths to the up-down routes that fat-tree routing actually uses.

## 12. AI assistance disclosure

This project was developed with the help of **Claude (Anthropic, Claude Opus 5.5), used
through Claude Code**. The AI read the assignment and the paper, wrote the code, tests
and README, ran the tests and experiments, and helped investigate the unexpected drop in
the average path length. All numbers in this README come from the actual program output
in `results/`. I reviewed the code and results and take responsibility for the submission.

## Reference

[1] M. Al-Fares, A. Loukissas, and A. Vahdat, "A scalable, commodity data center network
architecture," *Proc. ACM SIGCOMM 2008*, pp. 63–74, doi: 10.1145/1402946.1402967.
