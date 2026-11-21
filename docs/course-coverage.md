# Phạm vi offline theo môn học

Mỗi dòng `# @solve` dưới đây là một bài độc lập. Bôi đen một dòng rồi bấm **Alt+1**. Tool trả mã Python chạy độc lập và giải thích phạm vi của kết quả. Các ví dụ dùng dữ liệu tự tạo.

| Nguồn đã đối chiếu | Nhóm bài trong tool |
| --- | --- |
| Buổi 1 và slide Python cơ bản | Hàm tính tổng chẵn/lẻ, generator Fibonacci, phép toán vector, khử dấu và đếm ký tự để tính cosine |
| Thư mục buổi 2 | Thư mục trống trong bản tài liệu hiện có |
| Buổi 3 | Chưa tìm thấy thư mục. Phần tìm kiếm cơ bản lấy phạm vi từ slide Chương 3 |
| Buổi 4 và Chương 3–4 | BFS/UCS/DFS/DLS/IDS/Greedy/A* theo dữ liệu khai báo, sinh xâu, 8-puzzle, đối chiếu số ô sai và Manhattan, vết hill climbing |
| Buổi 5 và Chương 5 | N hậu, miền hữu hạn, tô màu với ràng buộc khác nhau, Sudoku, phép cộng chữ số, lập lịch, vết AC-3 |
| Buổi 6, bài nhóm và Chương 6 | Truy vấn dữ kiện quan hệ, so khớp biểu thức, số nguyên tố, bảng chân lý, SAT, hợp giải, Horn tiến/lùi |
| Chương 1–2 | Bốn cách tiếp cận AI, mô hình PEAS và kiểu tác tử. Bộ giải có ví dụ kế hoạch máy hút bụi và MDP hữu hạn |
| Chương 8 | Kế thừa frame, giá trị mặc định và mâu thuẫn giữa hai nhánh |
| Chương 9 | Bảng xác suất, xác suất có điều kiện, Bayes và phép toán tập mờ |

Với câu hỏi khái niệm, bốn cách tiếp cận trong Chương 1 phân biệt suy nghĩ và hành động theo hai chuẩn con người hoặc hợp lý. PEAS trong Chương 2 gồm thước đo hiệu quả, môi trường, cơ cấu chấp hành và cảm biến. Một đề về tác tử cần xác định thêm mức quan sát, tính xác định, số tác tử và sự thay đổi của môi trường.

## Python cơ bản

Tổng chẵn/lẻ nhận cả số âm và 0. Fibonacci nhận hai số đầu tùy chọn. Vector độ dài bất kỳ cần hai vế cùng chiều. Tính cosine từ văn bản mặc định khử dấu tiếng Việt và đếm 24 ký tự từ a đến x. Đặt `alphabet` để thay bảng chữ.

```python
# @solve {"type":"parity_sum","values":[-3,0,4,7]}
# @solve {"type":"fibonacci","count":6,"initial":[0,1]}
# @solve {"type":"vector_metrics","left":[1,2,3],"right":[3,2,1]}
# @solve {"type":"text_cosine","left":"Đá quý","right":"da quy"}
```

## Tác tử và tìm kiếm

Máy hút bụi được mô hình hóa với các phòng xếp thành hàng và một tập cấu hình bẩn có thể xảy ra. Vị trí ban đầu có thể là một phòng hoặc danh sách các phòng có thể có mặt. Vết chạy tìm kiếm giữ thứ tự cạnh đã khai báo. UCS tối ưu chi phí, BFS và IDS tối ưu số cạnh. A* kiểm tra heuristic trước khi báo bảo đảm tối ưu.

Sinh xâu dùng cây tiền tố, mỗi bước nối một ký tự và có chi phí 1. Bộ giải tính số nút được xét theo thứ tự `alphabet` kể cả khi cây quá lớn để duyệt thực tế.

```python
# @solve {"type":"vacuum_plan","rooms":2,"position":[0,1],"possible_dirty":[[],[0],[1],[0,1]],"first_action":"right"}
# @solve {"type":"search_trace","start":"A","goals":["G"],"edges":[["A","B",2],["A","G",5],["B","G",1]],"algorithm":"astar","heuristic":{"A":3,"B":1,"G":0}}
# @solve {"type":"string_search","goal":"ABC","alphabet":"ABC","algorithm":"ids"}
# @solve {"type":"puzzle_heuristics","start":[1,2,3,4,0,6,7,5,8],"goal":[1,2,3,4,5,6,7,8,0]}
# @solve {"type":"hill_climbing","scores":{"A":1,"B":1,"C":3},"edges":[["A","B"],["B","C"]],"start":"A","goal":"C","sideways_limit":1}
```

## Ràng buộc

Với N hậu, `fixed` và `blocked` dùng tọa độ `[cột,hàng]` từ 0. Chế độ `count` đếm từng cấu hình, kể cả đối xứng. AC-3 nhận một phép so sánh hai biến hoặc bảng `allowed`. Làm rỗng miền chứng minh vô nghiệm. Còn giá trị ở tất cả miền chỉ xác nhận phù hợp cung.

```python
# @solve {"type":"nqueens","n":5,"mode":"count","fixed":[[0,0]],"blocked":[[2,3]]}
# @solve {"type":"ac3","domains":{"A":["đỏ","xanh"],"B":["đỏ"]},"constraints":[{"vars":["A","B"],"op":"ne"}]}
```

## Logic và tri thức

Bảng chân lý nhận biểu thức dạng tiền tố và trả phản ví dụ nếu kết luận sai. Hợp giải nhận CNF với `!` đứng trước literal phủ định. Truy vấn quan hệ dùng `{"var":"tên"}` làm biến. So khớp biểu thức nhận miền hữu hạn cho biến và xử lý giao hoán, kết hợp của `+` và `*`. Frame giữ các nguồn mâu thuẫn khi hai nhánh độc lập cùng khai báo một thuộc tính.

```python
# @solve {"type":"entailment","premises":[["implies","P","Q"],"P"],"query":"Q"}
# @solve {"type":"resolution","clauses":[["!P","Q"],["P"]],"query":["Q"]}
# @solve {"type":"backward_horn","facts":["A"],"rules":[{"if":["A"],"then":"B"}],"query":"B"}
# @solve {"type":"relation","facts":{"parent":[["A","B"],["B","C"]]},"where":[{"relation":"parent","args":["A",{"var":"middle"}]},{"relation":"parent","args":[{"var":"middle"},{"var":"child"}]}],"select":["child"]}
# @solve {"type":"primes","values":[-2,1,2,49,101],"count":7}
# @solve {"type":"expression_match","pattern":["+",{"var":"x"},["*",2,{"var":"y"}]],"target":["+",["*",3,2],4],"domains":{"x":[3,4],"y":[2,3]}}
# @solve {"type":"frame_inheritance","frames":{"bird":{"slots":{"flies":true}},"penguin":{"parents":["bird"],"slots":{"flies":false}},"p":{"parents":["penguin"]}},"query":"p","slots":["flies"]}
```

## Xác suất và tập mờ

Bảng dữ liệu nhận số đếm hoặc trọng số. Cột của từng hàng theo thứ tự biến đã khai báo. Bayes nhận xác suất dưới dạng phân số hoặc số thập phân. Nếu khai báo nhiều quan sát riêng, cần đặt `conditional_independence` khi bài cho phép nhân các khả năng có điều kiện. Lát cắt α gồm cả phần tử nằm đúng ngưỡng.

```python
# @solve {"type":"conditional_probability","variables":{"wind":[true,false],"play":["yes","no"]},"rows":[[[true,"yes"],3],[[true,"no"],5],[[false,"yes"],4],[[false,"no"],2]],"query":{"play":"yes"},"evidence":{"wind":true}}
# @solve {"type":"bayes","priors":{"A":"2/5","B":"3/5"},"likelihoods":{"A":"3/4","B":"1/12"},"query":"A"}
# @solve {"type":"fuzzy_set","operation":"alpha_cut","left":{"x":"3/10","y":"1/2","z":0},"alpha":"3/10"}
```

## Giới hạn

Các dạng đã khai báo dùng thuật toán có giới hạn đầu vào và khối lượng tính toán. Kết quả hill climbing mô tả lần chạy cụ thể. Bộ giải quan hệ làm việc trên các dữ kiện hữu hạn. Các câu tự luận mở, logic bậc nhất tổng quát và những bài yêu cầu đúng một thư viện hoặc thuật toán ngoài các lựa chọn trong đặc tả vẫn cần đối chiếu với tài liệu.
