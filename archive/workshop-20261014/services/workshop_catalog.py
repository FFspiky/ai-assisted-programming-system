"""Original teaching scenes: Python produces bounded data; the browser only draws it."""

from copy import deepcopy

OCEAN_CODE = """import json, math, random, sys
p = json.load(sys.stdin)
rng = random.Random(p["seed"])
count = p["count"]
fish = [[rng.uniform(180, 820), rng.uniform(130, 520)] for _ in range(count)]
frames = []
for step in range(72):
    # 改变目标轨迹，试试鱼群会怎样转弯。
    target_x = 500 + 260 * math.cos(step / 16)
    target_y = 325 + 170 * math.sin(step / 12)
    for i, point in enumerate(fish):
        dx = target_x - point[0]
        dy = target_y - point[1]
        angle = math.atan2(dy, dx) + math.sin(step / 8 + i) * p["spread"] / 100
        point[0] = max(30, min(970, point[0] + math.cos(angle) * p["speed"] * 4))
        point[1] = max(30, min(620, point[1] + math.sin(angle) * p["speed"] * 4))
    frames.append([[round(x), round(y)] for x, y in fish])
print(json.dumps({"scene": "ocean", "frames": frames}, separators=(",", ":")))
"""

SORT_CODE = """import json, random, sys
p = json.load(sys.stdin)
rng = random.Random(p["seed"])
values = rng.sample(range(15, 100), p["count"])
frames = [{"values": values[:], "focus": [], "swapped": False}]
if p["algorithm"] == "bubble":
    for end in range(len(values) - 1, 0, -1):
        changed = False
        for j in range(end):
            swapped = values[j] > values[j + 1]
            if swapped:
                values[j], values[j + 1] = values[j + 1], values[j]
                changed = True
            frames.append({"values": values[:], "focus": [j, j + 1], "swapped": swapped})
        if not changed:
            break
else:
    for i in range(1, len(values)):
        j = i
        while j > 0:
            swapped = values[j - 1] > values[j]
            if swapped:
                values[j - 1], values[j] = values[j], values[j - 1]
            frames.append({"values": values[:], "focus": [j - 1, j], "swapped": swapped})
            if not swapped:
                break
            j -= 1
print(json.dumps({"scene": "sorting", "frames": frames}, separators=(",", ":")))
"""

ROUTE_CODE = """import collections, heapq, json, random, sys
p = json.load(sys.stdin)
rng = random.Random(p["seed"])
width, height = 14, 10
start, goal = (0, 9), (13, 0)
# 保留底边和右边航道，使内置地图至少有一条可行路线。
walls = {(x, y) for y in range(height) for x in range(width)
         if y != 9 and x != 13 and rng.random() < p["density"]}
walls.discard(goal)
parent, visited = {start: None}, []
queue = collections.deque([start])
heap = [(0, 0, start)]
cost = {start: 0}
while queue if p["algorithm"] == "bfs" else heap:
    node = queue.popleft() if p["algorithm"] == "bfs" else heapq.heappop(heap)[2]
    if node in visited:
        continue
    visited.append(node)
    if node == goal:
        break
    x, y = node
    for dx, dy in [(1, 0), (0, -1), (-1, 0), (0, 1)]:
        nxt = (x + dx, y + dy)
        if not (0 <= nxt[0] < width and 0 <= nxt[1] < height) or nxt in walls:
            continue
        next_cost = cost[node] + 1
        if nxt in cost and cost[nxt] <= next_cost:
            continue
        cost[nxt], parent[nxt] = next_cost, node
        if p["algorithm"] == "bfs":
            queue.append(nxt)
        else:
            estimate = abs(nxt[0] - goal[0]) + abs(nxt[1] - goal[1])
            heapq.heappush(heap, (next_cost + estimate, next_cost, nxt))
path = []
if goal in parent:
    node = goal
    while node is not None:
        path.append(node)
        node = parent[node]
    path.reverse()
print(json.dumps({"scene": "route", "width": width, "height": height,
                  "walls": sorted(walls), "visited": visited, "path": path}, separators=(",", ":")))
"""

SCENES = {
    "ocean": {
        "id": "ocean",
        "name": "鱼群共舞",
        "eyebrow": "01 / MOTION",
        "concept": "循环 · 向量 · 群体运动",
        "description": "让每一条鱼跟随自己的规则，汇成一片流动的海。",
        "title": "向光而游",
        "code": OCEAN_CODE,
        "prompt": "让鱼群游得更舒展，像在缓慢的潮汐中穿行。",
        "controls": [
            {
                "key": "count",
                "label": "鱼群数量",
                "type": "int",
                "min": 6,
                "max": 18,
                "step": 1,
                "default": 14,
            },
            {
                "key": "speed",
                "label": "游动速度",
                "type": "float",
                "min": 0.5,
                "max": 6,
                "step": 0.5,
                "default": 2.5,
            },
            {
                "key": "spread",
                "label": "散开程度",
                "type": "int",
                "min": 0,
                "max": 100,
                "step": 5,
                "default": 40,
            },
            {
                "key": "seed",
                "label": "随机种子",
                "type": "int",
                "min": 0,
                "max": 9999,
                "step": 1,
                "default": 42,
            },
        ],
        "contract": '输出 {"scene":"ocean","frames":[[[x,y],...],...] }；1–72 帧，每帧 1–18 个点，x 在 0–1000，y 在 0–650。',
    },
    "sorting": {
        "id": "sorting",
        "name": "排序编舞",
        "eyebrow": "02 / RHYTHM",
        "concept": "比较 · 交换 · 排序",
        "description": "把比较与交换变成节奏，观察秩序怎样一点点出现。",
        "title": "秩序的节奏",
        "code": SORT_CODE,
        "prompt": "改用插入排序，保留每次比较，让我观察数字怎样找到自己的位置。",
        "controls": [
            {
                "key": "count",
                "label": "舞者数量",
                "type": "int",
                "min": 5,
                "max": 16,
                "step": 1,
                "default": 12,
            },
            {
                "key": "algorithm",
                "label": "编舞规则",
                "type": "select",
                "options": {"bubble": "冒泡排序", "insertion": "插入排序"},
                "default": "bubble",
            },
            {
                "key": "seed",
                "label": "随机种子",
                "type": "int",
                "min": 0,
                "max": 9999,
                "step": 1,
                "default": 42,
            },
        ],
        "contract": '输出 {"scene":"sorting","frames":[{"values":[...],"focus":[...],"swapped":false},...] }；最多 160 帧，每帧 1–16 个 1–100 的整数，focus 为有效下标。',
    },
    "route": {
        "id": "route",
        "name": "海岛寻路",
        "eyebrow": "03 / EXPLORATION",
        "concept": "队列 · 图搜索 · 路径规划",
        "description": "画出探索的足迹，带一艘小船穿过群岛，找到灯塔。",
        "title": "去灯塔的路",
        "code": ROUTE_CODE,
        "prompt": "用 A* 搜索去寻找灯塔，保留探索顺序和最终路线。",
        "controls": [
            {
                "key": "density",
                "label": "岛屿密度",
                "type": "float",
                "min": 0.05,
                "max": 0.4,
                "step": 0.05,
                "default": 0.25,
            },
            {
                "key": "algorithm",
                "label": "探索策略",
                "type": "select",
                "options": {"bfs": "广度优先 BFS", "astar": "启发搜索 A*"},
                "default": "bfs",
            },
            {
                "key": "seed",
                "label": "随机种子",
                "type": "int",
                "min": 0,
                "max": 9999,
                "step": 1,
                "default": 42,
            },
        ],
        "contract": '输出 {"scene":"route","width":14,"height":10,"walls":[[x,y],...],"visited":[[x,y],...],"path":[[x,y],...] }；起点 [0,9]，终点 [13,0]，路径必须四方向相邻且不穿墙；无路可用空 path。',
    },
}


def scene_spec(scene):
    if scene not in SCENES:
        raise ValueError("请选择鱼群共舞、排序编舞或海岛寻路")
    return deepcopy(SCENES[scene])


def normalize_params(scene, value):
    spec = scene_spec(scene)
    if not isinstance(value, dict):
        raise ValueError("创作参数必须是对象")
    allowed = {c["key"] for c in spec["controls"]}
    if set(value) - allowed:
        raise ValueError("存在当前主题不支持的参数")
    params = {}
    for control in spec["controls"]:
        key = control["key"]
        item = value.get(key, control["default"])
        if control["type"] == "select":
            if not isinstance(item, str) or item not in control["options"]:
                raise ValueError(f"{control['label']}选项无效")
        else:
            import math

            if type(item) not in (int, float) or not math.isfinite(item):
                raise ValueError(f"{control['label']}必须是有限数字")
            if control["type"] == "int" and type(item) is not int:
                raise ValueError(f"{control['label']}必须是整数")
            if not control["min"] <= item <= control["max"]:
                raise ValueError(f"{control['label']}超出允许范围")
        params[key] = item
    return params
