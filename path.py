import heapq
import matplotlib.pyplot as plt
import numpy as np
import math

# --- CONFIG ---
SQUARES_X, SQUARES_Y = 12, 10
SQUARE_SIZE = 2.0      # inches per square
STEP = 1               # fine-grid step
ROWS = int(SQUARES_Y * SQUARE_SIZE / STEP)
COLS = int(SQUARES_X * SQUARE_SIZE / STEP)

# --- Start & Goal positions (in inches) ---
start_in = (2, 3)   # (y, x)
goal_in = (16, 3)

def to_grid(pos):
    y, x = pos
    return int(y / STEP), int(x / STEP)

start = to_grid(start_in)
goal = to_grid(goal_in)

# --- Obstacles: row 3, all columns (integer squares only) ---
pieces = {(3, i) for i in range(SQUARES_X+1)}  # (3,0)...(3,12)

# Inflate obstacles to fine grid: only block the **center of the square**
cells_per_square = int(SQUARE_SIZE / STEP)
obstacles = set()
for (r, c) in pieces:
    center_r = r * cells_per_square + cells_per_square // 2
    center_c = c * cells_per_square + cells_per_square // 2
    if 0 <= center_r < ROWS and 0 <= center_c < COLS:
        obstacles.add((center_r, center_c))

# --- A* Implementation ---
def heuristic(a, b):
    # Manhattan distance is appropriate with only up/down/left/right
    return abs(a[0]-b[0]) + abs(a[1]-b[1])

def neighbors(node):
    r, c = node
    # Only 4-connected moves
    for dr, dc in [(1,0), (-1,0), (0,1), (0,-1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < ROWS and 0 <= nc < COLS:
            yield (nr, nc)

def a_star(start, goal):
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}

    while open_set:
        _, current = heapq.heappop(open_set)
        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            return path[::-1]

        for neighbor in neighbors(current):
            if neighbor in obstacles:
                continue
            step_cost = 1.0  # no diagonal
            tentative_g = g_score[current] + step_cost
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + heuristic(neighbor, goal)
                heapq.heappush(open_set, (f, neighbor))
    return None

path = a_star(start, goal)

# --- Visualization ---
grid = np.zeros((ROWS, COLS))
for (r, c) in obstacles:
    grid[r, c] = 1

plt.figure(figsize=(COLS/10, ROWS/10))
plt.imshow(grid, cmap='gray_r', origin='upper')

if path:
    pr, pc = zip(*path)
    plt.plot(pc, pr, 'r-', linewidth=2)
    plt.scatter(pc[0], pr[0], c='green', s=100, label='Start')
    plt.scatter(pc[-1], pr[-1], c='blue', s=100, label='Goal')
else:
    print("No path found!")

plt.title("A* Path Between Obstacles (No Diagonals, 0.5 step allowed)")
plt.gca().invert_yaxis()
plt.legend()
plt.show()
