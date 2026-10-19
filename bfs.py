"""Breadth-first search on an unweighted adjacency-list graph."""

from collections import deque


def bfs_distances(adj, src):
    """Hop distance from `src` to every node reachable from it."""
    dist = {src: 0}
    queue = deque([src])
    while queue:
        u = queue.popleft()
        for v in adj[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                queue.append(v)
    return dist


def shortest_path_length(adj, src, dst):
    """Number of links on a shortest src-dst path, or None if disconnected.

    Standard BFS that stops as soon as `dst` is discovered.
    """
    if src == dst:
        return 0
    dist = {src: 0}
    queue = deque([src])
    while queue:
        u = queue.popleft()
        for v in adj[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                if v == dst:
                    return dist[v]
                queue.append(v)
    return None
