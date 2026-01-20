from collections import defaultdict
from typing import Dict, List, Set

from app.models.entities import Task


def build_conflict_graph(tasks: List[Task]) -> Dict[str, Set[str]]:
    graph: Dict[str, Set[str]] = defaultdict(set)
    for i, t1 in enumerate(tasks):
        for t2 in tasks[i + 1 :]:
            shared = set(t1.required_resources) & set(t2.required_resources)
            if shared:
                graph[t1.id].add(t2.id)
                graph[t2.id].add(t1.id)
    return graph
