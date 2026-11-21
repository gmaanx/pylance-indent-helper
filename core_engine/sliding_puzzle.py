"""Shortest-path solver for the 3×3 sliding puzzle."""

from heapq import heappop, heappush


def _puzzle_parity(board):
    tiles = [tile for tile in board if tile != 0]
    return sum(left > right for index, left in enumerate(tiles) for right in tiles[index + 1:]) % 2


def _puzzle_neighbors(board):
    blank = board.index(0)
    row, col = divmod(blank, 3)
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        next_row, next_col = row + dr, col + dc
        if 0 <= next_row < 3 and 0 <= next_col < 3:
            other = 3 * next_row + next_col
            moved = list(board)
            moved[blank], moved[other] = moved[other], moved[blank]
            yield tuple(moved)


def _solve_sliding_puzzle(start, goal):
    """Return a shortest path of boards, or None for unreachable goals."""
    # A 3×3 puzzle preserves the parity of the numbered tiles.
    if _puzzle_parity(start) != _puzzle_parity(goal):
        return None
    target_positions = {tile: divmod(index, 3) for index, tile in enumerate(goal)}

    def manhattan(board):
        distance = 0
        for index, tile in enumerate(board):
            if tile != 0:
                row, col = divmod(index, 3)
                goal_row, goal_col = target_positions[tile]
                distance += abs(row - goal_row) + abs(col - goal_col)
        return distance

    queue = [(manhattan(start), 0, start)]
    distances = {start: 0}
    parent = {start: None}
    while queue:
        _, distance, board = heappop(queue)
        if distance != distances[board]:
            continue
        if board == goal:
            path = []
            while board is not None:
                path.append(board)
                board = parent[board]
            return path[::-1]
        for neighbor in _puzzle_neighbors(board):
            new_distance = distance + 1
            if neighbor not in distances or new_distance < distances[neighbor]:
                distances[neighbor] = new_distance
                parent[neighbor] = board
                heappush(queue, (new_distance + manhattan(neighbor), new_distance, neighbor))
    return None
