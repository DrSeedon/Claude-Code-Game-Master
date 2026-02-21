"""Force-directed spring layout for interior node graphs. Returns {node: {x, y}} positions."""

import math
import random

_cache: dict = {}

_K_REPEL = 50000
_K_ATTRACT = 0.01
_K_ANCHOR = 0.05
_DAMPING = 0.9
_MIN_DIST = 10


def _cache_key(nodes, edges):
    return (frozenset(nodes), frozenset(edges))


def compute_layout(nodes, edges, entry_points=None, width=800, height=600, iterations=100):
    if not nodes:
        return {}

    key = _cache_key(nodes, edges)
    if key in _cache:
        return _cache[key]

    entry_set = set(entry_points or [])
    rng = random.Random(42)

    pos = {}
    for node in nodes:
        if node in entry_set:
            side = rng.randint(0, 3)
            if side == 0:
                pos[node] = [rng.uniform(0, width), rng.uniform(0, height * 0.1)]
            elif side == 1:
                pos[node] = [rng.uniform(0, width), rng.uniform(height * 0.9, height)]
            elif side == 2:
                pos[node] = [rng.uniform(0, width * 0.1), rng.uniform(0, height)]
            else:
                pos[node] = [rng.uniform(width * 0.9, width), rng.uniform(0, height)]
        else:
            pos[node] = [rng.uniform(width * 0.1, width * 0.9), rng.uniform(height * 0.1, height * 0.9)]

    node_list = list(nodes)

    for _ in range(iterations):
        forces = {node: [0.0, 0.0] for node in node_list}

        for i in range(len(node_list)):
            for j in range(i + 1, len(node_list)):
                a = node_list[i]
                b = node_list[j]
                dx = pos[a][0] - pos[b][0]
                dy = pos[a][1] - pos[b][1]
                dist = max(math.sqrt(dx * dx + dy * dy), _MIN_DIST)
                f = _K_REPEL / (dist * dist)
                fx = f * dx / dist
                fy = f * dy / dist
                forces[a][0] += fx
                forces[a][1] += fy
                forces[b][0] -= fx
                forces[b][1] -= fy

        for (src, dst) in edges:
            if src not in pos or dst not in pos:
                continue
            dx = pos[dst][0] - pos[src][0]
            dy = pos[dst][1] - pos[src][1]
            dist = max(math.sqrt(dx * dx + dy * dy), _MIN_DIST)
            f = _K_ATTRACT * dist
            fx = f * dx / dist
            fy = f * dy / dist
            forces[src][0] += fx
            forces[src][1] += fy
            forces[dst][0] -= fx
            forces[dst][1] -= fy

        for node in entry_set:
            if node not in pos:
                continue
            x, y = pos[node]
            nearest_edge_x = min(x, width - x)
            nearest_edge_y = min(y, height - y)
            if nearest_edge_x < nearest_edge_y:
                target_x = 0.0 if x < width / 2 else width
                forces[node][0] += _K_ANCHOR * (target_x - x)
            else:
                target_y = 0.0 if y < height / 2 else height
                forces[node][1] += _K_ANCHOR * (target_y - y)

        for node in node_list:
            pos[node][0] = max(0.0, min(width, pos[node][0] + forces[node][0] * _DAMPING))
            pos[node][1] = max(0.0, min(height, pos[node][1] + forces[node][1] * _DAMPING))

    result = {node: {"x": pos[node][0], "y": pos[node][1]} for node in node_list}
    _cache[key] = result
    return result
