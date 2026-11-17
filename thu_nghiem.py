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

