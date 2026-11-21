import ast
import contextlib
import io
import json
import unittest
from collections import deque

from core_engine.engine_pipeline import process_request


def reference_distances(goal):
    """Independently enumerate distances using the fixed 3×3 adjacency table."""
    adjacent = ((1, 3), (0, 2, 4), (1, 5), (0, 4, 6), (1, 3, 5, 7),
                (2, 4, 8), (3, 7), (4, 6, 8), (5, 7))
    distances = {goal: 0}
    queue = deque([goal])
    while queue:
        board = queue.popleft()
        blank = board.index(0)
        for other in adjacent[blank]:
            child = list(board)
            child[blank], child[other] = child[other], child[blank]
            child = tuple(child)
            if child not in distances:
                distances[child] = distances[board] + 1
                queue.append(child)
    return distances


class SlidingPuzzleTests(unittest.TestCase):
    def solve(self, start, goal):
        request = {"type": "sliding_puzzle", "start": start, "goal": goal, "algorithm": "astar"}
        result = process_request("# @solve " + json.dumps(request), "instant")
        self.assertEqual(result.validation_status, "verified", result.error_detail)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(result.code, {"__name__": "__main__"})
        return ast.literal_eval(output.getvalue())

    def test_exact_lengths_against_independent_bfs(self):
        goal = (1, 2, 3, 4, 5, 6, 7, 8, 0)
        samples = {}
        for board, distance in reference_distances(goal).items():
            samples.setdefault(distance, board)
        for distance in (0, 1, 2, 10, 20, 25, 30, 31):
            with self.subTest(distance=distance):
                start = samples[distance]
                path = self.solve(start, goal)
                self.assertEqual((path[0], path[-1], len(path) - 1), (start, goal, distance))
                for before, after in zip(path, path[1:]):
                    left, right = before.index(0), after.index(0)
                    self.assertEqual(abs(left // 3 - right // 3) + abs(left % 3 - right % 3), 1)
                    self.assertEqual([i for i in range(9) if before[i] != after[i]], sorted((left, right)))

    def test_reports_unreachable_custom_goal(self):
        start = (1, 2, 3, 4, 5, 6, 7, 8, 0)
        goal = (2, 1, 3, 4, 5, 6, 7, 8, 0)
        self.assertIsNone(self.solve(start, goal))


if __name__ == "__main__":
    unittest.main()
