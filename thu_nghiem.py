"""
Câu 1: Cho bài toán 8-puzzle với trạng thái ban đầu:
((1, 2, 3), (4, 0, 6), (7, 5, 8))
và trạng thái đích ((1, 2, 3), (4, 5, 6), (7, 8, 0)).
Hãy cài đặt bằng thư viện simpleai và giải bằng thuật toán A* với 2 hàm heuristic h1 và h2.
"""

"""
Bài toán Thỏa mãn ràng buộc - CSP (simpleai.search.csp)
Đề bài:
Phân công ca trực cho 4 nhân viên variables = ['An', 'Binh', 'Chi', 'Dung'] vào 3 ca làm việc ['Sang', 'Chieu', 'Toi'] sao cho thỏa mãn các ràng buộc sau:

An chỉ có thể làm ca 'Sang' hoặc 'Chieu'.

An và Binh không được làm cùng một ca.

Binh và Chi không được làm cùng một ca.

Chi và Dung phải làm khác ca nhau, đồng thời Dung không làm ca 'Sang'.

Yêu cầu: Sử dụng CspProblem và backtrack trong simpleai.search.csp để tìm một bộ phân công hợp lệ.
"""

"""
Bài 1.2: Lớp NutTimKiem (Node cho bài toán tìm kiếm)
Viết lớp NutTimKiem dùng biểu diễn nút trong thuật toán tìm kiếm:
__init__(self, state, parent=None, action=None, g=0.0, h=0.0): lưu các thuộc tính state, parent, action, g (chi phí từ nút gốc), h (chi phí ước lượng đến đích).
f_cost(self): trả về tổng chi phí $f(n) = g(n) + h(n)$ (dùng cho tìm kiếm $A^*$).
truy_vet_duong_di(self): đi ngược từ nút hiện tại qua parent đến nút gốc, trả về danh sách (list) các trạng thái theo thứ tự từ đầu đến đích.
"""

"""
Bài 2.1: Vector hóa nguyên âm & Khoảng cách / Độ tương đồng
Cho một chuỗi văn bản tiếng Anh:
Viết hàm vector_nguyen_am(text: str) -> list[int] đếm tần suất xuất hiện của 5 nguyên âm "aeiou" (không phân biệt chữ hoa/chữ thường nhờ .lower()), trả về danh sách gồm 5 số nguyên theo đúng thứ tự 'a', 'e', 'i', 'o', 'u'.
Viết hàm do_tuong_dong_cosine(v1: list[int], v2: list[int]) -> float tính độ tương đồng Cosine giữa hai vector cùng độ dài:
$$\text{sim}(v_1, v_2) = \frac{\sum v_{1,k} v_{2,k}}{\sqrt{\sum v_{1,k}^2} \cdot \sqrt{\sum v_{2,k}^2}}$$
Lưu ý biên: nếu một trong hai vector có chuẩn/độ dài bằng 0 (ví dụ chuỗi không có nguyên âm nào), trả về 0.0 để không bị lỗi chia cho 0.
"""

"""
Bài 4.1: Cài đặt BFS và DFS trên đồ thị (dict)
Cho đồ thị có hướng/vô hướng biểu diễn bằng từ điển (dict), ví dụ:
Python
graph = {
    "A": ["B", "C"],
    "B": ["D", "E"],
    "C": ["F"],
    "D": [],
    "E": ["F"],
    "F": []
}

Viết hàm bfs(graph, start, goal) sử dụng hàng đợi FIFO (list.pop(0) hoặc collections.deque) và tập visited để tìm đường đi từ start đến goal (trả về danh sách đường đi hoặc None nếu không tới được).
Viết hàm dfs(graph, start, goal) sử dụng ngăn xếp LIFO (list.pop()) để tìm đường đi từ start đến goal.
"""

"""
Bài 4.2: Kiểm tra ràng buộc / Suy diễn logic mệnh đề đơn giản
Cho các biến mệnh đề có giá trị True / False lưu trong dict, ví dụ:
Python
facts = {"C": True, "A": True, "R": True, "I": False, "D": True}
Với các quy tắc suy diễn:
$C \land A \rightarrow Q$
$R \land I \rightarrow H$
$Q \land H \land D \rightarrow E$
$E \rightarrow S$
Viết hàm suy_dien_tien(facts: dict[str, bool]) -> dict[str, bool] suy ra giá trị của Q, H, E, S từ facts ban đầu (A -> B tương đương (not A) or B).
Viết hàm dem_rang_buoc_vi_pham(assignment: dict[str, bool], clauses: list[list[tuple[str, bool]]]) -> int (gợi ý cho hàm đánh giá trong CSP / Local Search): mỗi mệnh đề tuyển (clause) là danh sách các cặp (ten_bien, can_gia_tri_dung); đếm xem có bao nhiêu mệnh đề không được thỏa mãn dưới phép gán assignment.
"""
