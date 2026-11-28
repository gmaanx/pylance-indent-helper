"""Request code suggestions from explicitly enabled model providers."""

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .config_manager import CONFIG
from .contract_checker import check_api_contract, extract_prompt_api_names, extract_prompt_typed_signatures
from .golden_skeletons import RETRIEVER, SIMPLEAI_STRICT_RULES, strip_accents
from .runnable_output import ensure_runnable_print, has_meaningful_runnable_main, prompt_forbids_print
from .workspace_context import is_starter_template


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_CLOUD_OPENER = build_opener(_NoRedirect())
_LOCAL_OPENER = build_opener(ProxyHandler({}), _NoRedirect())
_RESPONSE_LIMIT = 2_000_000
_OLLAMA_URL = "http://127.0.0.1:11434"
_CLOUD_CONFIG = (
    ("gemini", "https://generativelanguage.googleapis.com/v1beta/models/", "gemini-2.5-flash"),
    ("groq", "https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
    ("deepseek", "https://api.deepseek.com/chat/completions", "deepseek-chat"),
    ("openrouter", "https://openrouter.ai/api/v1/chat/completions", "qwen/qwen-2.5-coder-32b-instruct:free"),
    ("openai", "https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
)


def extract_python_code(raw_response: str) -> str:
    if not isinstance(raw_response, str) or not raw_response.strip():
        return ""
    text = raw_response.strip()
    match = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    text = re.sub(r"^```(?:python|py)?\s*", "", text, flags=re.IGNORECASE)
    return re.sub(r"```\s*$", "", text).strip()


_AI_RULE_KEYWORDS = (
    "simpleai", "kanren", "minikanren", "searchproblem", "cspproblem",
    "hill_climbing", "simulated_annealing", "arc_consistency",
    "convert_to_binary", "most_constrained_variable", "least_constraining_value",
)


def _needs_ai_library_rules(text: str) -> bool:
    folded = strip_accents(text).casefold()
    if "khong dung simpleai" in folded or ("python thuan" in folded and "simpleai" not in folded and "kanren" not in folded):
        return False
    return any(keyword in folded for keyword in _AI_RULE_KEYWORDS)

_STDIN_KEYWORDS = (
    "stdin", "ban phim", "input()", "nhap tu ban phim", "doc tu ban phim",
    "nhap vao tu", "doc dau vao", "sys.stdin",
)


def _prompt_requests_stdin(text: str) -> bool:
    folded = strip_accents(text).casefold()
    return any(keyword in folded for keyword in _STDIN_KEYWORDS)


def _runnable_output_guidance(user_prompt: str) -> str:
    if _prompt_requests_stdin(user_prompt):
        io_rule = (
            "- Đọc đúng dữ liệu đầu vào theo quy định của đề và chỉ in kết quả theo đúng định dạng yêu cầu."
        )
    else:
        io_rule = (
            "- Nếu đề có yêu cầu định dạng đầu ra (làm tròn, JSON, từng dòng, nhãn...), "
            "chỉ in kết quả theo đúng định dạng yêu cầu của đề.\n"
            "- Không dùng `input()`; gán sẵn dữ liệu mẫu từ đề (hoặc dữ liệu minh họa nhỏ hợp lệ) ngay trong `main()`."
        )
    return (
        "QUY TẮC BẮT BUỘC VỀ HÀM main() VÀ IN KẾT QUẢ KHI CHẠY:\n"
        "- Khi viết lời giải mới (không phải sửa mã có sẵn và đề không cấm ví dụ chạy thử), "
        "LUÔN định nghĩa `def main():` và kết thúc file bằng:\n"
        'if __name__ == "__main__":\n'
        "    main()\n"
        "- Trong `main()`, BẮT BUỘC gọi đúng hàm hoặc khởi tạo đúng lớp và gọi các phương thức vừa cài đặt theo đề, "
        "rồi print kết quả thực tế ra màn hình.\n"
        "- Không viết `main()` rỗng hoặc chỉ in chuỗi giữ chỗ vô nghĩa không gọi lời giải.\n"
        "- Định nghĩa hàm/lớp trước rồi viết `def main():` ở cuối file; đặt tên biến trong `main()` khác tên hàm/lớp (vd: `ket_qua = ...`).\n"
        f"{io_rule}\n"
        "- Giữ nguyên tên lớp, tên hàm và chữ ký API theo đề. Tôn trọng mọi yêu cầu bỏ ví dụ hoặc giữ nguyên đầu ra khi sửa mã có sẵn."
    )


def select_relevant_skeletons(
    query: str,
    *,
    top_k: int = 2,
    min_score: float = 12.0,
    for_local_model: bool = False,
) -> List[Dict[str, Any]]:
    if not query or not query.strip():
        return []
    folded = strip_accents(query).casefold()
    needs_ai_lib = _needs_ai_library_rules(query)
    req_classes, req_funcs, _ = extract_prompt_api_names(query)

    # CRITICAL: If the prompt prescribes custom functions/classes:
    # - For pure-Python prompts (not needs_ai_lib), NEVER inject mismatched skeletons!
    # - For small local models (1.5B/3B), even when using SimpleAI/Kanren, NEVER inject a 60-line
    #   global-variable demo skeleton if it doesn't define the requested API names (we inject an exact
    #   library API cheat-sheet instead so 1.5B never copy-pastes unrelated globals like GOAL/CAM/Nixon!).
    if (req_classes or req_funcs) and (not needs_ai_lib or for_local_model):
        candidates = RETRIEVER.retrieve(query, top_k=max(8, top_k * 3))
        matching = []
        for item in candidates:
            if item.get("score", 0.0) < min_score:
                continue
            skel_code = item.get("code", "")
            if check_api_contract(skel_code, query) == "":
                matching.append(item)
        return matching[:top_k]

    if "khong dung simpleai" in folded or ("python thuan" in folded and "simpleai" not in folded and "kanren" not in folded):
        if for_local_model:
            return []
        candidates = RETRIEVER.retrieve(query, top_k=top_k * 2)
        return [
            item for item in candidates
            if item.get("score", 0.0) >= min_score and "simpleai" not in item.get("code", "").lower()
        ][:top_k]

    if for_local_model and not needs_ai_lib:
        # For small local models, only inject non-SimpleAI skeletons on very high confidence
        candidates = RETRIEVER.retrieve(query, top_k=top_k)
        return [item for item in candidates if item.get("score", 0.0) >= 24.0]

    candidates = RETRIEVER.retrieve(query, top_k=top_k)
    return [item for item in candidates if item.get("score", 0.0) >= min_score]


def _ai_library_api_cheatsheet(text: str) -> str:
    """Concise, hallucination-free SimpleAI / Kanren API reference without distracting global demo variables."""
    folded = strip_accents(text).casefold()
    blocks: List[str] = []
    if "kanren" in folded or "minikanren" in folded:
        blocks.append(
            "API CHUẨN `kanren` (TUYỆT ĐỐI KHÔNG viết `def cha_me(...):` cho vị từ dữ liệu; vị từ PHẢI là đối tượng `Relation()`!):\n"
            "from kanren import Relation, facts, run, var, lall\n"
            "cha_me = Relation()  # BẮT BUỘC khởi tạo đối tượng Relation, KHÔNG định nghĩa hàm trùng tên!\n"
            "facts(cha_me, ('A', 'B'), ('B', 'C'))\n"
            "# Truy vấn trong hàm: x, y = var(), var(); return sorted(set(run(0, x, lall(cha_me(ong_ba, y), cha_me(y, x)))))"
        )
    if "simpleai" in folded or any(k in folded for k in ("searchproblem", "cspproblem", "hill_climbing_random_restarts")):
        if "cspproblem" in folded or "backtrack" in folded or ("csp" in folded and "searchproblem" not in folded):
            blocks.append(
                "API CHUẨN `simpleai` CSP (TUYỆT ĐỐI KHÔNG import `simpleai.search.constraints` vì KHÔNG tồn tại!):\n"
                "from simpleai.search import CspProblem, backtrack, MOST_CONSTRAINED_VARIABLE, HIGHEST_DEGREE_VARIABLE, LEAST_CONSTRAINING_VALUE, min_conflicts\n"
                "# Hàm điều kiện nhận `(variables, values)` trong đó `values` là TUPLE các giá trị số/chuỗi theo chỉ số `0, 1, 2...` (ví dụ 3 biến: `def cond(variables, values): return len(set(values)) == 3 and values[0] < values[1] and sum(values) == tong_muc_tieu`).\n"
                "# Danh sách ràng buộc: `constraints = [(('X', 'Y', 'Z'), cond)]` hoặc `[((u, v), lambda vars, vals: vals[0] != vals[1]) for u, v in edges]`.\n"
                "# Giải: `ket_qua = backtrack(CspProblem(list(domains.keys()), domains, constraints))` -> `ket_qua` ĐÃ LÀ `dict` (hoặc `None`), `return dict(ket_qua) if ket_qua is not None else None` (KHÔNG có `.state`!)."
            )
        if any(k in folded for k in ("hill_climbing", "simulated_annealing", "genetic", "local")):
            blocks.append(
                "API CHUẨN `simpleai.search.local`:\n"
                "from simpleai.search import SearchProblem\n"
                "from simpleai.search.local import hill_climbing, hill_climbing_random_restarts, simulated_annealing, beam, genetic\n"
                "# Lớp kế thừa `SearchProblem` cần:\n"
                "#   actions(self, state), result(self, state, action) -> tuple, value(self, state) -> float (CỰC ĐẠI HÓA `-dem_xung_dot(state)`),\n"
                "#   generate_random_state(self) -> `tuple(random.randrange(n) for _ in range(n))` (KHÔNG trả hằng số cố định!).\n"
                "# Chú ý cực kỳ quan trọng: `ket_qua = hill_climbing_random_restarts(problem, restarts_limit=50)` trả về đối tượng `SearchNode` -> "
                "phải lấy trạng thái qua `ket_qua.state` (ví dụ `return tuple(ket_qua.state)`, TUYỆT ĐỐI KHÔNG viết `tuple(ket_qua)`! Nếu đề cần 0 xung đột, lặp vài lần tới khi `dem_xung_dot(ket_qua.state) == 0`)."
            )
        if "searchproblem" in folded or any(k in folded for k in ("astar", "breadth_first", "depth_first", "uniform_cost", "greedy")):
            if not any(k in folded for k in ("hill_climbing", "simulated_annealing", "genetic")):
                extra_sp_lines: List[str] = []
                if "puzzle" in folded:
                    extra_sp_lines.append(
                        "# - Với 8-puzzle (tuple 9 số): trong `actions` dùng `idx = state.index(0); r, c = divmod(idx, 3)` trả danh sách chỉ số đích `nr * 3 + nc` hợp lệ; "
                        "trong `result` dùng `idx = state.index(0); s = list(state); s[idx], s[action] = s[action], s[idx]; return tuple(s)`; "
                        "Manhattan: `sum(abs(i // 3 - self.goal.index(v) // 3) + abs(i % 3 - self.goal.index(v) % 3) for i, v in enumerate(state) if v != 0)`."
                    )
                if "quan ma" in folded or "quan_ma" in folded or "knight" in folded:
                    extra_sp_lines.append(
                        "# - Với Quân Mã 8 hướng `MOVES = [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]`: `actions(self, state)` trả `[(r+dr, c+dc) for dr, dc in MOVES if 0 <= r+dr < 8 and 0 <= c+dc < 8 and (r+dr, c+dc) not in self.cam]`; `result(self, state, action)` trả `action`; "
                        "hàm giải gọi `node = breadth_first(problem, graph_search=True)` và trả `None if node is None else [st for act, st in node.path()]`."
                    )
                extra_txt = ("\n" + "\n".join(extra_sp_lines)) if extra_sp_lines else ""
                blocks.append(
                    "API CHUẨN `simpleai.search` (TUYỆT ĐỐI KHÔNG import `simpleai.search.heuristics` và KHÔNG đặt tên `goal_test`!):\n"
                    "from simpleai.search import SearchProblem, breadth_first, depth_first, uniform_cost, greedy, astar\n"
                    "# Lớp kế thừa `SearchProblem`: trong `__init__(self, start, goal, ...)`: gọi `super().__init__(start)` và lưu `self.goal = goal`.\n"
                    "# Phương thức: `actions(self, state)`, `result(self, state, action) -> tuple`, `is_goal(self, state) -> bool`, `cost(self, state, action, state2) -> 1`, `heuristic(self, state) -> float`."
                    + extra_txt + "\n"
                    "# - BẮT BUỘC: Nếu đề yêu cầu viết hàm giải (vd `def giai_...(start, goal=...)`), PHẢI định nghĩa hàm đó ở mức module bên ngoài class, bên trong hàm khởi tạo Problem, chạy `node = astar(problem, graph_search=True)` và `return int(node.cost)` (hoặc danh sách trạng thái theo đề), rồi `main()` gọi hàm đó!"
                )
    return "\n\n".join(blocks)


def _pure_python_domain_hints(user_prompt: str) -> str:
    folded = strip_accents(user_prompt).casefold()
    hints: List[str] = []
    if ("grid" in folded or "luoi" in folded or "me cung" in folded) and ("bfs" in folded or "tim_duong" in folded) and "simpleai" not in folded:
        hints.append(
            "- BFS đường đi ngắn nhất trên lưới 2D `grid`: kiểm tra `if not grid or grid[start[0]][start[1]] == 1 or grid[goal[0]][goal[1]] == 1: return None`; "
            "khởi tạo `queue = deque([start]); parent = {start: None}`; trong `while queue:`: lấy `r, c = queue.popleft()`, nếu `(r, c) == goal`: viết đủ vòng lặp truy vết `cur = goal; path = []; while cur is not None: path.append(cur); cur = parent[cur]; return path[::-1]`; "
            "với 4 hướng `(nr, nc)` đi được chưa có trong `parent`: `parent[(nr, nc)] = (r, c); queue.append((nr, nc))`."
        )
    elif ("bfs" in folded or "dfs" in folded) and "dict" in folded and "simpleai" not in folded:
        hints.append(
            "- BFS/DFS tìm đường trên `dict`: kiểm tra `if start == goal: return [start]`; khởi tạo `queue = deque([(start, [start])])` và `visited = {start}`; lấy `cur, path = queue.popleft()` và trả `[start, ..., goal]` hoặc `None`."
        )
    if "cosine" in folded or ("chuan" in folded and "chia cho 0" in folded):
        hints.append(
            "- Độ tương đồng Cosine: tính `norm1 = math.sqrt(sum(x*x for x in v1))` và `norm2 = math.sqrt(sum(y*y for y in v2))`; "
            "BẮT BUỘC kiểm tra `if norm1 == 0 or norm2 == 0: return 0.0` (dùng `or`, KHÔNG dùng `and`) trước khi chia."
        )
    if "yen_ngua" in folded or ("nho nhat tren hang" in folded and "lon nhat tren cot" in folded):
        hints.append(
            "- Điểm yên ngựa trên ma trận `m x n`: kiểm tra `if not matrix or not matrix[0]: return []`; tính `row_mins = [min(row) for row in matrix]` (1 số mỗi hàng) "
            "và `col_maxs = [max(matrix[r][c] for r in range(len(matrix))) for c in range(len(matrix[0]))]` (1 số mỗi cột), rồi lấy `[(r, c) for r in range(len(matrix)) for c in range(len(matrix[0])) if matrix[r][c] == row_mins[r] and matrix[r][c] == col_maxs[c]]`."
        )
    if "rle" in folded or "run-length" in folded or ("nen_chuoi" in folded and "giai_nen" in folded):
        hints.append(
            "- Run-Length Encoding gồm 2 hàm KHÁC NHAU:\n"
            "  + Hàm NÉN (`nen_chuoi_rle(s)`): đếm ký tự giống nhau liên tiếp `i = 0; out = []; while i < len(s): j = i; while j < len(s) and s[j] == s[i]: j += 1; out.append(f'{s[i]}{j - i}'); i = j; return ''.join(out)`.\n"
            "  + Hàm GIẢI NÉN (`giai_nen_rle(encoded)`): tách chữ cái rồi gom chữ số `i = 0; out = []; while i < len(encoded): ch = encoded[i]; i += 1; num = ''; while i < len(encoded) and encoded[i].isdigit(): num += encoded[i]; i += 1; out.append(ch * (int(num) if num else 1)); return ''.join(out)`."
        )
    if ("hangdoiuutien" in folded or "uu tien" in folded or "muc_cap_cuu" in folded) and "fifo" in folded:
        hints.append(
            "- Hàng đợi ưu tiên lớn nhất + FIFO bằng `import heapq`: vì `heapq` là min-heap nên khởi tạo `self._heap = []; self._seq = 0`; "
            "khi thêm đẩy `heapq.heappush(self._heap, (-muc_cap_cuu, self._seq, ten)); self._seq += 1`; khi lấy ra `return heapq.heappop(self._heap)[2]` (hoặc `None` nếu rỗng)."
        )
    if "suy_dien" in folded or ("facts" in folded and ("->" in user_prompt or "rightarrow" in folded or "horn" in folded)):
        if "set[" in folded or "tap tat ca" in folded or "tap ket qua" in folded:
            hints.append(
                "- Suy diễn tiến trả về `set[str]`: khởi tạo `known = {k for k, v in facts.items() if v}`; lặp với cờ `changed = True`: "
                "`while changed: changed = False; for tien_de, ket_luan in rules: if ket_luan not in known and all(p in known for p in tien_de): known.add(ket_luan); changed = True`; cuối cùng `return known` (TUYỆT ĐỐI KHÔNG dùng `while True` thiếu cờ `changed`)."
            )
        else:
            hints.append(
                "- Suy diễn tiến (Modus Ponens) trên `facts: dict`: khởi tạo `kq = dict(facts)` và gán mặc định `False` cho các biến kết luận chưa có; "
                "lặp suy diễn với cờ `changed`: với mỗi quy tắc `A and B -> Q`, nếu các tiền đề đều `True` (`kq.get('A', False) and ...`) thì `kq['Q'] = True`."
            )
    if "menh de tuyen" in folded or "clauses" in folded or "rang_buoc_vi_pham" in folded:
        hints.append(
            "- Đếm mệnh đề tuyển (OR clause) vi phạm: mỗi `clause` được thỏa mãn nếu `any(assignment.get(bien) == gia_tri_dung for bien, gia_tri_dung in clause)`; "
            "nếu `not thoa_man` thì tăng biến đếm vi phạm lên 1."
        )
    if "is_a" in folded or "mangngunghia" in folded or ("ke thua" in folded and "ghi de" in folded):
        hints.append(
            "- Mạng ngữ nghĩa kế thừa `is_a`: khởi tạo `self.parents = {}` và `self.attrs = {}`; "
            "`them_is_a`: `self.parents.setdefault(con, []).append(cha)`; "
            "`gan_thuoc_tinh`: `self.attrs.setdefault(khainiem, {})[ten_tt] = gia_tri`; "
            "`tra_cuu`: duyệt `queue = deque([khainiem]); visited = {khainiem}`, mỗi bước `cur = queue.popleft(); if ten_tt in self.attrs.get(cur, {}): return self.attrs[cur][ten_tt]`, rồi đẩy `for cha in self.parents.get(cur, []):` nếu chưa có trong `visited`."
        )
    if "balo" in folded or "knapsack" in folded or "cai tui" in folded:
        hints.append(
            "- Quy hoạch động cái túi 0/1 (`0/1 Knapsack`): bảng `dp` kích thước `(n + 1) x (capacity + 1)`; khi truy vết ngược `i` từ `n` về `1`, nếu `dp[i][w] != dp[i - 1][w]` thì chỉ số món được chọn theo hệ 0-based là `i - 1` (`chosen.append(i - 1)`; `w -= weights[i - 1]`), cuối cùng đảo ngược `chosen.reverse()`."
        )
    if "bayes" in folded and "priors" in folded and "likelihoods" in folded:
        hints.append(
            "- Cập nhật Bayes trên `dict`: tính `numer = {h: priors[h] * likelihoods.get(h, 0.0) for h in priors}` và `p_e = sum(numer.values())` (KHÔNG lấy `sum(likelihoods.values())`!); "
            "nếu `p_e == 0`: trả `{h: 0.0 for h in priors}`, ngược lại trả `{h: numer[h] / p_e for h in priors}`."
        )
    if "hau" in folded or "queen" in folded:
        hints.append(
            "- Bài toán N-Queens (mỗi cột `i` đặt hậu ở hàng `state[i]`): hai quân hậu `i < j` ăn nhau khi `state[i] == state[j] or abs(state[i] - state[j]) == j - i`. "
            "Trong `SearchProblem` tìm kiếm cục bộ: viết chính xác `def actions(self, state): return [(c, r) for c in range(len(state)) for r in range(len(state)) if r != state[c]]` "
            "và `def result(self, state, action): c, r = action; s = list(state); s[c] = r; return tuple(s)`; "
            "trong hàm giải viết `ket_qua = None; for _ in range(15): ket_qua = hill_climbing_random_restarts(problem, restarts_limit=50); if dem_xung_dot(ket_qua.state) == 0: break; return tuple(ket_qua.state)`."
        )
    if "knn" in folded or "k-nearest" in folded or "lang gieng" in folded:
        hints.append(
            "- Phân lớp K-NN: tính `dists = [(math.sqrt(sum((a - b) ** 2 for a, b in zip(x, x_query))), idx, y) for idx, (x, y) in enumerate(zip(train_x, train_y))]`, "
            "`k_near = sorted(dists)[:k]`, đếm phiếu `votes = Counter(y for _, _, y in k_near)` và từ điển tổng khoảng cách `sum_d = {lb: sum(d for d, _, y in k_near if y == lb) for lb in votes}` (phải là `dict`, KHÔNG phải `list`!), "
            "chọn `max(votes, key=lambda lb: (votes[lb], -sum_d[lb]))`."
        )
    return "LƯU Ý THUẬT TOÁN & XỬ LÝ BIÊN BẮT BUỘC:\n" + "\n".join(hints) if hints else ""


def _compact_skeleton_for_local(code: str, max_lines: int = 35) -> str:
    """Strip docstrings and comments from a Golden Skeleton WITHOUT ever slicing mid-class or dropping helpers."""
    import ast as _ast

    cleaned_src = code
    if hasattr(_ast, "unparse"):
        try:
            tree = _ast.parse(code)
            for node in _ast.walk(tree):
                if isinstance(node, (_ast.Module, _ast.ClassDef, _ast.FunctionDef, _ast.AsyncFunctionDef)):
                    if (
                        node.body
                        and isinstance(node.body[0], _ast.Expr)
                        and isinstance(getattr(node.body[0], "value", None), _ast.Constant)
                        and isinstance(node.body[0].value.value, str)
                    ):
                        node.body.pop(0)
                        if not node.body:
                            node.body.append(_ast.Pass())
            cleaned_src = _ast.unparse(tree)
            # Only if still long, drop top-level `if __name__ == "__main__":` block cleanly at AST boundary
            if len(cleaned_src.splitlines()) > max_lines:
                trimmed_body = [
                    stmt for stmt in tree.body
                    if not (
                        isinstance(stmt, _ast.If)
                        and isinstance(stmt.test, _ast.Compare)
                        and isinstance(stmt.test.left, _ast.Name)
                        and stmt.test.left.id == "__name__"
                    )
                ]
                if trimmed_body:
                    tree.body = trimmed_body
                    cleaned_src = _ast.unparse(tree)
        except Exception:
            cleaned_src = code

    lines = [
        raw_ln for raw_ln in cleaned_src.splitlines()
        if raw_ln.strip() and not raw_ln.strip().startswith("#")
    ]
    return "\n".join(lines)


def _ollama_perf_options(total_chars: int) -> Dict[str, Any]:
    """High-throughput AVX2 batch + smart physical-core thread sizing for fast, lag-free CPU inference."""
    logical_cpus = os.cpu_count() or 4
    if logical_cpus >= 12:
        safe_threads = 8
    elif logical_cpus >= 8:
        safe_threads = 6
    elif logical_cpus >= 6:
        safe_threads = 5
    elif logical_cpus >= 4:
        safe_threads = 3
    else:
        safe_threads = max(1, logical_cpus)
    num_ctx = 4096
    num_predict = 1280 if total_chars < 3200 else 1536
    return {
        "temperature": 0.0,
        "repeat_penalty": 1.08,
        "num_ctx": num_ctx,
        "num_batch": 512,
        "num_predict": num_predict,
        "num_thread": safe_threads,
    }


def build_context_injected_prompt(
    user_prompt: str,
    top_skeletons: List[Dict[str, Any]],
    existing_code: str = "",
    error_traceback: str = "",
    *,
    workspace_context: str = "",
    for_local: bool = False,
) -> Tuple[str, str]:
    req_cls, req_fns, _ = extract_prompt_api_names(user_prompt)
    typed_sigs = {fn: f"def {fn}({inner}) -> {rt}:" for fn, inner, rt in extract_prompt_typed_signatures(user_prompt)}
    must_items = [
        *(f"class {c}:" for c in req_cls),
        *(typed_sigs.get(f, f"def {f}(...):") for f in req_fns),
    ]

    if for_local and error_traceback.strip():
        repair_sections = [
            "Bạn là trình sửa lỗi Python chính xác 100%. Chỉ xuất TOÀN BỘ file Python đã sửa trong ```python ... ```, KHÔNG giải thích, KHÔNG viết comment.\n"
            "Đọc kỹ `Chi tiết lỗi cần sửa ngay` để sửa đúng dòng bị lỗi, khai báo mọi biến/hàm thiếu, kiểm tra số phần tử khi unpack tuple và giữ nguyên `if __name__ == \"__main__\":\\n    main()`."
        ]
        if must_items:
            repair_sections.append(
                "BẮT BUỘC PHẢI ĐỊNH NGHĨA ĐẦY ĐỦ TẤT CẢ CÁC LỚP VÀ HÀM ĐỘC LẬP SAU Ở MỨC MODULE (NGOÀI `main()`):\n"
                + "\n".join(must_items)
            )
        domain_hints = _pure_python_domain_hints(user_prompt)
        if domain_hints:
            repair_sections.append(domain_hints)
        lib_cheatsheet = _ai_library_api_cheatsheet(f"{user_prompt}\n{existing_code}")
        if lib_cheatsheet:
            repair_sections.append(lib_cheatsheet)
        system_prompt = "\n\n".join(repair_sections)
    elif for_local:
        io_line = (
            "Đọc dữ liệu stdin theo đề và chỉ print kết quả theo đúng định dạng yêu cầu."
            if _prompt_requests_stdin(user_prompt)
            else "Không dùng `input()`; gán sẵn dữ liệu mẫu hợp lệ trong `def main():` và print kết quả thực tế theo đúng định dạng yêu cầu."
        )
        sections = [
            "Chuyên gia giải thuật Python 10/10. Chỉ xuất mã Python thuần trong ```python ... ```, KHÔNG giải thích, KHÔNG viết comment để sinh mã nhanh nhất.\n"
            "QUY TẮC BẮT BUỘC:\n"
            "1. Import đầy đủ thư viện dùng trong bài (`import math`, `import heapq`, `from collections import deque, Counter`, ...). Đúng 100% tên lớp/hàm, thứ tự tham số, kiểu trả về (`-> int` không trả `bool`; tìm đường trả `[start, ..., goal]` hoặc `None` nếu vô nghiệm; mọi hàm có kiểu trả về BẮT BUỘC có lệnh `return ket_qua`).\n"
            "2. BẮT BUỘC dùng trực tiếp tất cả tham số truyền vào hàm (TUYỆT ĐỐI KHÔNG dùng biến toàn cục ngoài hàm); không sửa trực tiếp `dict`/`list` đầu vào trừ khi đề yêu cầu; dùng `graph.get(u, [])`; kiểm tra mẫu số 0 trước khi chia.\n"
            f"3. {io_line} Trong `main()` BẮT BUỘC gọi trực tiếp các hàm/lớp vừa định nghĩa. Kết thúc bằng:\n"
            'if __name__ == "__main__":\n'
            "    main()"
        ]
        if must_items:
            sections.append(
                "BẮT BUỘC PHẢI VIẾT ĐẦY ĐỦ TẤT CẢ CÁC LỚP VÀ HÀM ĐỘC LẬP SAU Ở MỨC MODULE (NGOÀI `main()`, KHÔNG ĐƯỢC BỎ SÓT HÀM NÀO):\n"
                + "\n".join(must_items)
            )
        domain_hints = _pure_python_domain_hints(user_prompt)
        if domain_hints:
            sections.append(domain_hints)
        if existing_code.strip() and is_starter_template(existing_code) and not error_traceback.strip():
            sections.append("Giữ nguyên 100% chữ ký hàm/lớp của khung mã và hoàn thiện mọi `# TODO` / `pass` / `NotImplementedError`.")
        if top_skeletons and not error_traceback.strip():
            sections.append(
                "SimpleAI bắt buộc: `state` là `tuple` (không dùng `list`); `SearchProblem.__init__` gọi `super().__init__(initial_state)`; "
                "`bfs/dfs/astar(..., graph_search=True)`; hàm ràng buộc CSP có dạng `def cond(variables, values):`."
            )
            item = top_skeletons[0]
            compact_code = _compact_skeleton_for_local(item["code"])
            sections.append(f"Mẫu cú pháp ({item['title']} — chỉ tham khảo cú pháp API, giữ đúng tên/dữ liệu của đề):\n{compact_code}")
        else:
            lib_cheatsheet = _ai_library_api_cheatsheet(f"{user_prompt}\n{existing_code}")
            if lib_cheatsheet:
                sections.append(lib_cheatsheet)
            elif _needs_ai_library_rules(f"{user_prompt}\n{existing_code}"):
                sections.append(
                    "SimpleAI bắt buộc: `state` là `tuple` (không dùng `list`); `SearchProblem.__init__` gọi `super().__init__(initial_state)`; "
                    "`bfs/dfs/astar(..., graph_search=True)`; hàm ràng buộc CSP có dạng `def cond(variables, values):`."
                )
        if workspace_context and workspace_context.strip():
            sections.append(workspace_context.strip()[:1200])
        system_prompt = "\n\n".join(sections)
    else:
        sections = [
            "Bạn là chuyên gia giải thuật & lập trình Python đạt độ chính xác tuyệt đối. "
            "Giữ nguyên toàn bộ dữ liệu, thuật toán, định dạng đầu ra và mọi ràng buộc phụ trong yêu cầu. "
            "Nếu dùng mẫu tham khảo, bỏ dữ liệu ví dụ và thay bằng đúng dữ liệu của yêu cầu. "
            "Chỉ trả về mã Python gọn sạch, KHÔNG viết comment dài dòng để tối ưu tốc độ.\n"
            "5 NGUYÊN TẮC BẮT BUỘC ĐỂ ĐẠT 10 ĐIỂM TUYỆT ĐỐI:\n"
            "1. Đúng 100% tên lớp, tên hàm, thứ tự tham số, giá trị mặc định và kiểu trả về (`-> int` không trả `bool`; bài tìm đường `-> list` phải lưu vết đầy đủ `[start, ..., goal]`, không trả 1 đỉnh cuối; trả `None` khi vô nghiệm nếu đề yêu cầu).\n"
            "2. Không làm biến đổi trực tiếp (`pop`, `clear`, gán đè) lên `dict`/`list`/`set` đầu vào của người gọi trừ khi đề yêu cầu sửa tại chỗ.\n"
            "3. Xử lý chặt mọi biên: dữ liệu rỗng, vật cản, `start == goal`, đỉnh lá không có trong khóa `dict` (`graph.get(u, [])`), trạng thái mở rộng trong `visited` (vd `(r, c, pin)` nếu có năng lượng/chìa khóa), mẫu số bằng 0 (`norm1 == 0 or norm2 == 0`).\n"
            "4. Khi dùng `heapq` cho UCS / Greedy / A*, luôn kèm `counter = itertools.count()` ở phần tử thứ 2 `(priority, next(counter), state, ...)`.\n"
            "5. Cài đặt đầy đủ mọi hàm/phương thức (không để `pass` / `TODO`), trong `main()` dùng ví dụ có nghiệm hợp lệ để in kết quả thực tế, tương thích Python 3.8+."
        ]
        req_cls, req_fns, req_meths = extract_prompt_api_names(user_prompt)
        typed_sigs = {fn: f"def {fn}({inner}) -> {rt}:" for fn, inner, rt in extract_prompt_typed_signatures(user_prompt)}
        if req_cls or req_fns:
            must_items = [
                *(f"class {c}:" for c in req_cls),
                *(typed_sigs.get(f, f"def {f}(...):") for f in req_fns),
            ]
            sections.append(
                "BẮT BUỘC PHẢI VIẾT ĐẦY ĐỦ TẤT CẢ CÁC LỚP VÀ HÀM ĐỘC LẬP SAU Ở MỨC MODULE (NGOÀI `main()`, KHÔNG ĐƯỢC BỎ SÓT HÀM NÀO):\n"
                + "\n".join(must_items)
            )
        domain_hints = _pure_python_domain_hints(user_prompt)
        if domain_hints:
            sections.append(domain_hints)
        if existing_code.strip() and is_starter_template(existing_code) and not error_traceback.strip():
            sections.append(
                "CHẾ ĐỘ ĐIỀN KHUYẾT KHUNG ĐỀ THI (# TODO / pass / NotImplementedError):\n"
                "- Giữ nguyên 100% tên lớp, tên hàm, danh sách tham số và cấu trúc khung code giảng viên đã cho.\n"
                "- Hoàn thiện đầy đủ tất cả các phần `# TODO`, `pass`, `...`, `NotImplementedError` theo đúng yêu cầu đề bài."
            )
        if top_skeletons or _needs_ai_library_rules(f"{user_prompt}\n{existing_code}"):
            sections.append(SIMPLEAI_STRICT_RULES.strip())
        if top_skeletons and not error_traceback.strip():
            examples = "\n\n".join(
                f"Mẫu tham khảo cú pháp ({item['title']} — CHỈ tham khảo cú pháp thư viện, KHÔNG chép tên hàm/dữ liệu nếu đề yêu cầu khác):\n{item['code']}"
                for item in top_skeletons[:2]
            )
            sections.append(examples)
        if workspace_context and workspace_context.strip():
            sections.append(workspace_context.strip())
        sections.append(_runnable_output_guidance(user_prompt))
        system_prompt = "\n\n".join(sections)

    parts = [f"Yêu cầu:\n{user_prompt}"]
    missing_api_repair = "Thiếu hàm bắt buộc" in error_traceback or "Thiếu lớp bắt buộc" in error_traceback
    if for_local and (not existing_code.strip() or missing_api_repair) and (not error_traceback.strip() or missing_api_repair) and req_fns:
        stub_lines: List[str] = []
        folded_up = strip_accents(user_prompt).casefold()
        needs_sp = "searchproblem" in folded_up or ("simpleai" in folded_up and "cspproblem" not in folded_up)
        if needs_sp and not req_cls and req_fns:
            stub_lines.append("class _SearchSolverProblem(SearchProblem):\n    ...")
        for c_name in req_cls:
            base_part = "(SearchProblem)" if (needs_sp and "Problem" in c_name) else ""
            stub_lines.append(f"class {c_name}{base_part}:\n    ...")
        for f_name in req_fns:
            sig_hdr = typed_sigs.get(f_name, f"def {f_name}(...):")
            stub_lines.append(f"{sig_hdr}\n    # Hàm độc lập mức module: gọi giải thuật và return kết quả đúng kiểu\n    ...")
        parts.append(
            "Khung chữ ký bắt buộc ở mức module (BẮT BUỘC giữ đủ cả lớp và hàm độc lập dưới đây):\n```python\n"
            + "\n\n".join(stub_lines)
            + "\n```"
        )
    if existing_code.strip():
        parts.append(f"Mã hiện tại:\n```python\n{existing_code.strip()}\n```")
    if error_traceback.strip():
        parts.append(
            f"Chi tiết lỗi cần sửa ngay:\n{error_traceback}\n\n"
            "HƯỚNG DẪN SỬA LỖI BẮT BUỘC: Hãy sửa triệt để lỗi trên trong `Mã hiện tại` "
            "(bổ sung đầy đủ mọi hàm/lớp còn thiếu ở mức module, khai báo đủ biến còn thiếu, bổ sung lệnh `return` đúng kiểu) "
            "và xuất lại TOÀN BỘ chương trình Python hoàn chỉnh trong ```python ... ```."
        )
    completing_template = bool(existing_code.strip()) and is_starter_template(existing_code) and not error_traceback.strip()
    if (not existing_code.strip() or completing_template) and not error_traceback.strip() and not prompt_forbids_print(user_prompt):
        input_hint = "" if _prompt_requests_stdin(user_prompt) else " (gán sẵn dữ liệu mẫu, không dùng `input()`)"
        must_tail = f" định nghĩa đủ ({', '.join([*req_cls, *(f'{fn}(...)' for fn in req_fns)])}) ở mức module," if (req_cls or req_fns) else ""
        parts.append(
            f'Viết chương trình Python hoàn chỉnh{must_tail} gồm `def main():` gọi đúng hàm/lớp theo đề{input_hint}, '
            'print kết quả thực tế theo đúng định dạng yêu cầu nếu có, và `if __name__ == "__main__":\\n    main()`.'
        )
    return system_prompt, "\n\n".join(parts)


def _post_json(opener, url, payload, timeout, headers=None):
    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with opener.open(req, timeout=timeout) as response:
        message = response.read(_RESPONSE_LIMIT + 1)
    if len(message) > _RESPONSE_LIMIT:
        raise ValueError("Provider response exceeds size limit")
    body = json.loads(message)
    if not isinstance(body, dict):
        raise ValueError("Unexpected provider response")
    return body


def _request_cloud(provider, endpoint, model, key, system_prompt, user_message, timeout):
    if provider == "gemini":
        body = _post_json(
            _CLOUD_OPENER,
            f"{endpoint}{quote(model, safe='')}:generateContent",
            {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_message}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192},
            },
            timeout,
            {"x-goog-api-key": key},
        )
        candidates = body.get("candidates") or []
        if not candidates or candidates[0].get("finishReason") in ("MAX_TOKENS", "SAFETY"):
            return ""
        parts = candidates[0].get("content", {}).get("parts") or []
        return "".join(part.get("text", "") for part in parts if not part.get("thought"))

    body = _post_json(
        _CLOUD_OPENER,
        endpoint,
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": 8192,
        },
        timeout,
        {"Authorization": f"Bearer {key}", "User-Agent": "PythonPracticeHelper/2.0"},
    )
    choices = body.get("choices") or []
    if not choices or choices[0].get("finish_reason") in ("length", "content_filter"):
        return ""
    return choices[0].get("message", {}).get("content", "")


def _provider_error(provider, exc):
    if isinstance(exc, HTTPError):
        detail = {
            400: "yêu cầu hoặc model không được hỗ trợ",
            401: "API key bị từ chối",
            403: "không có quyền gọi model",
            404: "không tìm thấy model hoặc API",
            429: "đã chạm hạn mức",
        }.get(exc.code, "lỗi từ máy chủ")
        return f"{provider}: HTTP {exc.code}, {detail}."
    if isinstance(exc, (URLError, TimeoutError, OSError)):
        return f"{provider} không kết nối được hoặc hết thời gian chờ."
    return f"{provider} trả về dữ liệu sai định dạng."


def call_tier1_cloud_llm(
    system_prompt: str,
    user_msg: str,
    *,
    diagnostics: Optional[List[str]] = None,
    provider_id: Optional[str] = None,
    max_attempts: Optional[int] = None,
    raw_response: bool = False,
) -> Optional[Tuple[str, str]]:
    messages = diagnostics if diagnostics is not None else []
    timeout = float(CONFIG.get("cloud_timeout", 8.0))
    attempts = 0
    for provider, endpoint, default_model in _CLOUD_CONFIG:
        if max_attempts is not None and attempts >= max_attempts:
            break
        if provider_id is not None and provider_id != provider:
            continue
        key = CONFIG.get_api_key(provider)
        if not key:
            continue
        attempts += 1
        model = CONFIG.get(f"{provider}_model", default_model)
        try:
            result = _request_cloud(provider, endpoint, model, key, system_prompt, user_msg, timeout)
        except (OSError, ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
            messages.append(_provider_error(provider, exc))
            continue
        if isinstance(result, str):
            result = result.strip() if raw_response else extract_python_code(result)
        if result and isinstance(result, str):
            return result, f"tier1_{provider}"
        messages.append(f"{provider} không trả về dữ liệu hoàn chỉnh.")
    if not attempts:
        messages.append("Chưa có API key cho phiên Cloud này.")
    return None


def _repair_ollama_main(model: str, user_prompt: str, draft_code: str, timeout: float) -> Optional[str]:
    """Fast surgical synthesis of ONLY `def main():` (~40 tokens, ~2s on CPU) instead of regenerating the whole file."""
    repair_system = (
        "Chỉ xuất duy nhất khối `def main():` và `if __name__ == \"__main__\":\\n    main()` bằng Python "
        "(KHÔNG chép lại các lớp/hàm đã có, KHÔNG giải thích, KHÔNG dùng `input()` trừ khi đề bắt buộc) "
        "để gọi đúng hàm/lớp trong mã hiện có với dữ liệu mẫu hợp lệ và print kết quả thực tế."
    )
    repair_prompt = (
        f"Đề bài:\n{user_prompt[:1200]}\n\n"
        f"Các hàm/lớp đã cài đặt:\n```python\n{draft_code}\n```\n\n"
        "Viết tiếp phần `def main():` và `if __name__ == \"__main__\":` ở cuối file:"
    )
    opts = _ollama_perf_options(len(repair_system) + len(repair_prompt))
    opts["num_predict"] = 320
    payload = {
        "model": model,
        "system": repair_system,
        "prompt": repair_prompt,
        "stream": False,
        "keep_alive": "90m",
        "options": opts,
    }
    try:
        body = _post_json(_LOCAL_OPENER, _OLLAMA_URL + "/api/generate", payload, min(timeout, 25.0))
    except (OSError, ValueError, RecursionError):
        return None
    if body.get("done") is not True or body.get("done_reason") in ("length", "load"):
        return None
    tail = extract_python_code(body.get("response", ""))
    if not tail:
        return None
    candidates_to_try = [tail]
    if "def main" in tail and tail.strip() != draft_code.strip():
        # Strip any prior dummy `def main` / `if __name__` tail from draft_code before appending surgical main()
        import ast as _ast
        prefix = draft_code.rstrip()
        try:
            tree = _ast.parse(draft_code)
            cut_line = None
            for node in tree.body:
                if isinstance(node, _ast.FunctionDef) and node.name == "main":
                    cut_line = node.lineno
                    break
                if (
                    isinstance(node, _ast.If)
                    and isinstance(node.test, _ast.Compare)
                    and isinstance(node.test.left, _ast.Name)
                    and node.test.left.id == "__name__"
                ):
                    cut_line = node.lineno
                    break
            if cut_line is not None and cut_line > 1:
                prefix = "\n".join(draft_code.splitlines()[: cut_line - 1]).rstrip()
        except Exception:
            pass
        if prefix:
            candidates_to_try.append(prefix + "\n\n\n" + tail.lstrip())
    for cand in candidates_to_try:
        try:
            compile(cand, "<ollama-repair>", "exec")
        except (SyntaxError, ValueError, OverflowError, RecursionError, MemoryError):
            continue
        if has_meaningful_runnable_main(cand, user_prompt):
            return cand
    return None


def review_local_draft(user_prompt: str, draft_code: str) -> str:
    """Run a bounded self-critique pass on Ollama for complex multi-constraint prompts."""
    if not draft_code or len(user_prompt.strip()) < 220 or "\n" not in user_prompt.strip():
        return draft_code
    model = CONFIG.get("local_model")
    if not isinstance(model, str) or not model.strip():
        return draft_code
    timeout = float(CONFIG.get("local_timeout", 90.0))
    audit_system = (
        "Bạn là giám khảo chấm thi thuật toán Python cực kỳ khắt khe. "
        "Hãy đối chiếu từng câu, từng điều kiện biên và công thức cập nhật trạng thái trong Đề bài với Bản nháp Python:\n"
        "1. Có bỏ sót vật cản / điều kiện cấm / điều kiện dừng nào trong đề không?\n"
        "2. Thứ tự cộng/trừ/nạp lại biến trạng thái đã đúng 100% từng chữ trong đề chưa?\n"
        "3. Cấu trúc `visited` đã xét đúng trạng thái mở rộng (ví dụ lưu mức năng lượng tốt nhất tại mỗi ô thay vì chỉ đánh dấu tọa độ `(x, y)` đơn thuần nếu đề cho phép quay lại khi nhiều pin hơn) chưa?\n"
        "4. Kiểu trả về, tên hàm, tham số và hàm `main()` đã đầy đủ chưa?\n"
        "Nếu bản nháp đã ĐÚNG TUYỆT ĐỐI 100%, chỉ trả về đúng từ: KEEP\n"
        "Nếu có BẤT KỲ sai sót hay thiếu sót nào, hãy trả về TOÀN BỘ mã Python hoàn chỉnh đã sửa đúng 100% trong khối ```python ... ```."
    )
    audit_prompt = (
        f"Đề bài gốc:\n{user_prompt}\n\n"
        f"Bản nháp Python cần rà soát:\n```python\n{draft_code}\n```\n"
    )
    payload = {
        "model": model,
        "system": audit_system,
        "prompt": audit_prompt,
        "stream": False,
        "options": {"temperature": 0.05, "num_ctx": 8192, "num_predict": 3072},
    }
    try:
        body = _post_json(_LOCAL_OPENER, _OLLAMA_URL + "/api/generate", payload, timeout)
    except Exception:
        return draft_code
    if not isinstance(body, dict) or body.get("done") is not True or body.get("done_reason") in ("length", "load"):
        return draft_code
    raw_resp = (body.get("response") or "").strip()
    if not raw_resp or raw_resp.upper() == "KEEP":
        return draft_code
    revised = extract_python_code(raw_resp)
    if not revised or revised.upper() == "KEEP":
        return draft_code
    try:
        compile(revised, "<local-audit>", "exec")
    except Exception:
        return draft_code
    return revised


def _is_real_local_opener() -> bool:
    return not hasattr(_post_json, "assert_called")


def _find_any_installed_local_model() -> Optional[str]:
    try:
        with _LOCAL_OPENER.open(_OLLAMA_URL + "/api/tags", timeout=1.5) as resp:
            data = json.loads(resp.read(500_000))
    except Exception:
        return None
    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, list):
        return None
    names: List[str] = []
    for entry in models:
        if not isinstance(entry, dict) or entry.get("remote_host") or entry.get("remote_model"):
            continue
        m_name = entry.get("name") or entry.get("model")
        if isinstance(m_name, str) and m_name.strip():
            low = m_name.casefold()
            if not low.endswith(("-cloud", ":cloud")) and "@cloud" not in low:
                names.append(m_name.strip())
    if not names:
        return None
    for preferred in names:
        if "qwen2.5-coder" in preferred.casefold():
            return preferred
    for preferred in names:
        if "coder" in preferred.casefold():
            return preferred
    return names[0]


def _try_wake_ollama_daemon() -> bool:
    import subprocess
    import sys
    import time
    try:
        from setup_lab.local_ai import find_ollama
    except Exception:
        return False
    ollama_exe = find_ollama()
    if ollama_exe is None or not ollama_exe.is_file():
        return False
    env = dict(os.environ, OLLAMA_HOST="127.0.0.1:11434", OLLAMA_NO_CLOUD="1")
    flags = 0
    if sys.platform == "win32":
        flags = (
            getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        )
    try:
        subprocess.Popen(
            [str(ollama_exe), "serve"],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
    except OSError:
        return False
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            with _LOCAL_OPENER.open(_OLLAMA_URL + "/api/tags", timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def is_local_ollama_ready() -> bool:
    """Fast loopback readiness check (auto-waking daemon if needed) for real local Ollama installations."""
    if not _is_real_local_opener():
        return False
    model = CONFIG.get("local_model")
    if not isinstance(model, str) or not model.strip():
        return False
    if model.casefold().endswith(("-cloud", ":cloud")) or "@cloud" in model.casefold():
        return False
    found = _find_any_installed_local_model()
    if found is None and _try_wake_ollama_daemon():
        found = _find_any_installed_local_model()
    return bool(found)


def call_tier2_local_llm(
    user_prompt: str,
    best_skeleton: Optional[Dict[str, Any]],
    existing_code: str = "",
    *,
    error_traceback: str = "",
    workspace_context: str = "",
    diagnostics: Optional[List[str]] = None,
    timeout_override: Optional[float] = None,
) -> Optional[Tuple[str, str]]:
    messages = diagnostics if diagnostics is not None else []
    system_prompt, user_msg = build_context_injected_prompt(
        user_prompt,
        [best_skeleton] if best_skeleton else [],
        existing_code,
        error_traceback=error_traceback,
        workspace_context=workspace_context,
        for_local=True,
    )
    # Guard against silent prompt truncation on a small local model.
    if len(user_msg.encode("utf-8")) > 12_000:
        messages.append("Đề quá dài cho chế độ AI cục bộ. Bôi đen một bài hoặc một phần mã ngắn hơn.")
        return None

    model = CONFIG.get("local_model")
    if not isinstance(model, str) or model.casefold().endswith(("-cloud", ":cloud")) or "@cloud" in model.casefold():
        messages.append("Chọn model Ollama được tải trên máy để dùng AI cục bộ.")
        return None
    timeout = float(timeout_override) if timeout_override is not None else float(CONFIG.get("local_timeout", 75.0))
    perf_opts = _ollama_perf_options(len(system_prompt) + len(user_msg))
    if error_traceback.strip():
        perf_opts["num_predict"] = min(perf_opts["num_predict"], 960)
        perf_opts["temperature"] = 0.2
    payload = {
        "model": model,
        "system": system_prompt,
        "prompt": user_msg,
        "stream": False,
        "keep_alive": "90m",
        "options": perf_opts,
    }
    try:
        try:
            details = _post_json(_LOCAL_OPENER, _OLLAMA_URL + "/api/show", {"model": model}, 5.0)
        except (URLError, TimeoutError, ConnectionError):
            if _is_real_local_opener() and _try_wake_ollama_daemon():
                details = _post_json(_LOCAL_OPENER, _OLLAMA_URL + "/api/show", {"model": model}, 5.0)
            else:
                raise
        except HTTPError as exc:
            if exc.code == 404 and _is_real_local_opener():
                alt_model = _find_any_installed_local_model()
                if alt_model and alt_model != model:
                    model = alt_model
                    payload["model"] = alt_model
                    details = _post_json(_LOCAL_OPENER, _OLLAMA_URL + "/api/show", {"model": model}, 5.0)
                else:
                    raise
            else:
                raise
        if details.get("remote_host") or details.get("remote_model"):
            messages.append("Model đã chọn dùng máy chủ từ xa. Hãy chọn model Ollama được tải trên máy.")
            return None
        body = _post_json(_LOCAL_OPENER, _OLLAMA_URL + "/api/generate", payload, timeout)
    except HTTPError as exc:
        if exc.code == 404:
            messages.append(f"Ollama chưa có model {model}. Chạy setup.bat (chọn [2]) để tải model.")
        else:
            messages.append(_provider_error("Ollama", exc))
        return None
    except (URLError, TimeoutError, ConnectionError):
        messages.append("Không kết nối được Ollama cục bộ hoặc hết thời gian chờ. Mở Ollama và thử lại.")
        return None
    except (OSError, ValueError, RecursionError):
        messages.append("Ollama trả dữ liệu không đọc được. Kiểm tra ứng dụng Ollama rồi thử lại.")
        return None

    code = extract_python_code(body.get("response", ""))
    if body.get("done") is True and body.get("done_reason") not in ("length", "load") and code:
        if not existing_code.strip() and not prompt_forbids_print(user_prompt):
            enhanced, has_meaningful = ensure_runnable_print(code, user_prompt)
            if has_meaningful and not _has_syntax_err(enhanced):
                code = enhanced
            elif not has_meaningful:
                repaired = _repair_ollama_main(model, user_prompt, code, timeout)
                if repaired:
                    code = repaired
        return code, "tier2_ollama"
    messages.append("Ollama chưa trả mã hoàn chỉnh. Thử yêu cầu ngắn hơn hoặc chọn model khác.")
    return None


def _has_syntax_err(src: str) -> bool:
    try:
        compile(src, "<chk>", "exec")
        return False
    except Exception:
        return True
