# Trợ lý bài tập Python

Tiện ích Windows hỗ trợ luyện bài Python trong VS Code hoặc Antigravity. Bộ giải offline hỗ trợ 42 dạng Python cơ bản, tìm kiếm, logic, tối ưu, xác suất và học máy có đặc tả. Với yêu cầu khác, tool có thể đưa ra mẫu tham khảo hoặc gửi yêu cầu đến nhà cung cấp Cloud do bạn chọn. Trong bài thi, dùng các chế độ mà quy chế cho phép.

## Cài đặt offline

1. Chuẩn bị Python 3.10 trở lên và VS Code hoặc Antigravity.
2. Giải nén gói Windows vào thư mục có thể ghi, rồi chạy [setup_nhanh.bat](setup_nhanh.bat). Nếu chạy từ mã nguồn, mở PowerShell trong thư mục repo và dùng lệnh bên dưới.
3. Trong IDE đang mở, bấm **Ctrl+Shift+P → Reload Window**. Mở file Python và thử một ví dụ ở phần dưới.

```powershell
py -3 setup.py
```

Nếu máy có lệnh `python` trỏ đúng phiên bản, có thể dùng `python setup.py`. Trình cài chọn IDE có sẵn, tạo môi trường Python riêng, dùng các wheel đi kèm và kiểm tra chức năng trước khi báo hoàn tất. Có thể chỉ định IDE hoặc kiểm tra điều kiện cài trước.

```powershell
py -3 setup.py --check
py -3 setup.py --ide vscode
py -3 setup.py --ide antigravity
```

Nếu IDE không có CLI, chạy `py -3 setup.py --ide manual`, sau đó chọn **Extensions → Install from VSIX** và mở file VSIX mà trình cài in ra.

Người đóng gói có thể tạo ZIP cài đặt bằng `py -3 setup_lab/build_release.py`. Gói nằm trong `dist/` và chứa một bộ wheel, mã runtime, extension và các script cần dùng.

## Dùng trong IDE

Viết yêu cầu trong một file `.py`. Để xử lý riêng một đoạn, bôi đen đoạn đó trước khi chạy lệnh. Tool mở cửa sổ so sánh, trong đó bạn có thể xem dữ liệu, kết quả và thay đổi dự kiến. Chọn **Áp dụng** khi đã kiểm tra. Nếu tài liệu thay đổi trong lúc xử lý, chạy lại lệnh trên bản mới.

| Phím | Lệnh |
| --- | --- |
| `Alt+1` | Giải offline từ yêu cầu hoặc dữ liệu có cấu trúc |
| `Alt+2` | Phân tích offline |
| `Alt+3` | Chọn nhà cung cấp và xác nhận yêu cầu Cloud |
| `Alt+4` | Xem đề xuất sửa code offline |
| `Alt+0` | Mở xác nhận gỡ công cụ |

Có thể tìm các lệnh trong **Ctrl+Shift+P**. Lệnh hủy hiện ở thông báo tiến độ khi đang xử lý. Bản cài dành cho IDE và các phím tạo code hoạt động khi đang soạn Python.

## Dùng bộ giải offline

Bộ giải đọc những câu mô tả đơn giản mà nó nhận diện được. Với dữ liệu dài hoặc cần kết quả có thể kiểm tra, viết một dòng comment `# @solve` chứa JSON. Đặt trong file riêng hoặc bôi đen đúng dòng đó trước khi chạy `Alt+1`.

Xem bảng đối chiếu bài tập theo từng buổi, các chương bài giảng và 21 ví dụ bổ sung. [Phạm vi offline theo môn học](docs/course-coverage.md)

### Đong nước

Mặc định, mỗi lần rót tới khi bình nguồn cạn hoặc bình đích đầy. Dùng `max_pour` nếu mỗi bước được chọn số lít từ 1 đến mức giới hạn. Dùng `blocked_jugs` để cấm rót vào hoặc ra khỏi các bình theo chỉ số từ 0.

```python
# @solve {"type":"water_jugs","capacities":[2,4,7,9],"start":[0,0,0,9],"goal":5,"algorithm":"bfs"}
```

### Đổi tiền

Tìm số đồng ít nhất. Mặc định mỗi mệnh giá có số lượng không giới hạn. Thêm `inventory` theo đúng thứ tự của `denominations` để giới hạn số đồng mỗi loại. Bài có giới hạn dùng quy hoạch động (`algorithm: "dp"`).

```python
# @solve {"type":"coin_change","amount":17,"denominations":[4,7,9],"algorithm":"bfs"}
# @solve {"type":"coin_change","amount":9,"denominations":[4,3,2],"inventory":[1,3,0],"algorithm":"dp"}
```

### Đường đi trên đồ thị

UCS tìm đường có tổng chi phí thấp nhất với trọng số không âm. Dùng `bellman_ford` cho trọng số âm. Nếu có thể đi từ điểm xuất phát qua một chu trình âm rồi tới đích, tool báo chi phí không có cận dưới.

```python
# @solve {"type":"graph","start":"A","goal":"C","edges":[["A","B",2],["B","C",1],["A","C",9]],"algorithm":"ucs","directed":true}
# @solve {"type":"graph","start":"A","goal":"C","edges":[["A","B",2],["B","C",-5],["A","C",3]],"algorithm":"bellman_ford","directed":true}
```

### Bài toán ràng buộc (CSP)

Ví dụ chọn giá trị trong từng miền sao cho hai biến nhận giá trị khác nhau.

```python
# @solve {"type":"csp","domains":{"A":[1,2],"B":[1,2]},"constraints":[{"op":"ne","vars":["A","B"]}]}
```

CSP nhận miền số nguyên, tối đa 24 biến. Các phép hỗ trợ gồm `eq`, `ne`, `lt`, `le`, `all_different` và `sum_eq`. Với `sum_eq`, dùng trường `value` để khai báo tổng. Đồ thị BFS dùng cạnh `[nguồn, đích]`, UCS dùng `[nguồn, đích, trọng số]` với trọng số nguyên không âm.

### 8-puzzle

Khai báo hai bảng dưới dạng danh sách 9 số theo thứ tự đọc từng hàng. Dùng `0` cho ô trống. A* tìm số bước trượt ít nhất hoặc báo đích không thể đạt tới.

```python
# @solve {"type":"sliding_puzzle","start":[1,2,3,4,0,6,7,5,8],"goal":[1,2,3,4,5,6,7,8,0],"algorithm":"astar"}
```

### Tìm đường có điều kiện và cây trò chơi

- `grid` dùng tọa độ `[hàng,cột]` từ 0, `#` là tường, `a` đến `f` là chìa khóa và `A` đến `F` là cửa tương ứng. `visit` khai báo các điểm phải ghé. `visit_order: "ordered"` yêu cầu ghé đúng thứ tự, kể cả khi đường ngắn hơn đi qua điểm sau trước. `moves` chọn `cardinal`, `diagonal` hoặc `knight`. `costs` đặt chi phí khi vào từng loại ô. Với bước chéo, mặc định phải đi được cả hai ô kề ở góc.
- `minimax` dùng số cho nút lá và danh sách cho các nút con. `root` chọn bên đi trước `max` hoặc `min`. Dùng `algorithm: "minimax"` để xét toàn cây hoặc `"alpha_beta"` để cắt nhánh. Nếu đặt `depth_limit`, nút trong tại mức cắt phải khai báo cả `children` và `heuristic`.

```python
# @solve {"type":"grid","rows":[".A.",".a."],"start":[0,0],"goal":[0,2],"visit":[[0,1]]}
# @solve {"type":"minimax","tree":[[3,5],[2,9]],"root":"min","algorithm":"alpha_beta"}
```

### Logic và ràng buộc

SAT đọc mệnh đề CNF hoặc văn bản DIMACS có dòng `p cnf`. Horn suy diễn tiến theo các luật dương. Sudoku phân biệt vô nghiệm, một nghiệm và nhiều nghiệm. Phép cộng chữ số hỗ trợ cơ số 2–16, chữ khác nhau nhận chữ số khác nhau.

```python
# @solve {"type":"sat","variables":3,"clauses":[[1,-2],[2,3],[-3]]}
# @solve {"type":"horn","facts":["A"],"rules":[{"if":["A"],"then":"B"}],"query":"B"}
# @solve {"type":"sudoku","grid":[[0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]}
# @solve {"type":"cryptarithm","addends":["SEND","MORE"],"result":"MONEY","base":10}
```

### Tối ưu và lập lịch

Knapsack 0/1 có thể yêu cầu chọn đúng số món và giữ món bắt buộc. TSP hỗ trợ cạnh có hướng, cạnh thiếu và hành trình không quay về. Lập lịch khoảng thời gian dùng một tài nguyên. Lập lịch phụ thuộc tính đường găng khi công việc độc lập có thể chạy song song.

```python
# @solve {"type":"knapsack","capacity":7,"items":[["A",4,8],["B",3,7],["C",2,5]],"required":["C"],"count":2}
# @solve {"type":"tsp","nodes":["A","B","C"],"start":"A","edges":[["A","B",2],["B","C",3]],"directed":true,"return_to_start":false,"end":"C"}
# @solve {"type":"interval_scheduling","intervals":[["A",0,4,10],["B",0,2,6],["C",2,4,6]]}
# @solve {"type":"precedence_scheduling","tasks":[["A",3],["B",5],["C",2]],"dependencies":[["A","C"],["B","C"]]}
```

### Phân công, luồng và rừng khung

- `assignment` ghép mọi phần tử ở `left` với các phần tử khác nhau ở `right`, chỉ dùng cạnh đã khai báo. `objective` chọn `min` hoặc `max`.
- `max_flow` trả giá trị luồng, luồng trên từng cạnh và lát cắt nhỏ nhất để đối chiếu.
- `minimum_spanning_forest` dùng Kruskal trên đồ thị vô hướng. Khi đồ thị rời rạc, kết quả giữ từng thành phần, kể cả đỉnh cô lập.

```python
# @solve {"type":"assignment","left":["An","Bình"],"right":["A","B"],"edges":[["An","A",1],["An","B",4],["Bình","A",2]],"objective":"min"}
# @solve {"type":"max_flow","nodes":["s","a","t"],"source":"s","sink":"t","edges":[["s","a",3],["a","t",2],["s","t",1]]}
# @solve {"type":"minimum_spanning_forest","nodes":["A","B","C","D"],"edges":[["A","B",1],["B","C",2],["A","C",5]]}
```

### Học máy và quyết định

- `knn` phân lớp theo khoảng cách Euclid. Có thể chuẩn hóa min–max dựa trên tập huấn luyện. Khi hòa phiếu, ưu tiên lớp có mẫu gần nhất rồi xét thứ tự tên lớp.
- `id3` xây cây cho đặc trưng phân loại bằng độ lợi thông tin. Giá trị chưa gặp dùng lớp đa số ở nút hiện tại và được đánh dấu trong kết quả.
- `mdp` tìm chính sách tối ưu cho số bước hữu hạn đã khai báo. Mỗi hành động cần tổng xác suất bằng 1. Dùng `{}` cho trạng thái kết thúc.

```python
# @solve {"type":"knn","train":[{"x":[0,0],"label":"A"},{"x":[2,1],"label":"B"}],"query":[1,0],"k":1,"normalize":"minmax"}
# @solve {"type":"id3","train":[{"x":["sunny"],"label":"no"},{"x":["rainy"],"label":"yes"}],"query":["sunny"]}
# @solve {"type":"mdp","states":{"S":{"stay":[{"to":"S","p":1,"reward":1}],"close":[{"to":"T","p":1,"reward":5}]},"T":{}},"discount":0.9,"horizon":3}
```

Mỗi dòng `@solve` là một ví dụ độc lập. Bôi đen một dòng trước khi bấm `Alt+1`. Bộ giải cũng nhận một số câu tiếng Việt về đong nước, đổi tiền, 8-puzzle và minimax khi nhận diện được toàn bộ nội dung.

**Đã giải theo đặc tả** nghĩa là bộ giải offline đã tính kết quả theo dữ liệu và quy tắc được hỗ trợ. Bài vượt giới hạn, có dữ liệu thiếu hoặc dùng ràng buộc chưa hỗ trợ sẽ có thông báo riêng. Mẫu tham khảo và đề xuất Cloud cần được đối chiếu với đề. **Đã kiểm tra cú pháp** xác nhận Python đọc được đoạn code.

## Lấy và dùng API key

Cloud là lựa chọn theo từng yêu cầu. Trong IDE, bấm `Alt+3`, chọn hãng, nhập key tại ô che ký tự và xác nhận nội dung sẽ gửi. Key được giữ trong bộ nhớ của phiên IDE. Dùng lệnh **Quên API key phiên này** để xóa ngay. File cấu hình key kiểu cũ có thể vẫn nằm trong bản nguồn bạn từng dùng.

Cloud dùng tối đa hai lượt gọi cùng nhà cung cấp. Lượt sau rà bản nháp với nguyên văn đề, gồm dữ liệu, thuật toán, ràng buộc, định dạng kết quả và các ca biên. Tool tính độc lập tối đa bốn ca nhỏ do model trích từ đề. Nếu một dự đoán sai so với bộ giải, IDE giữ nguyên tệp và hiển thị mâu thuẫn. Phép đối chiếu chỉ áp dụng cho dữ kiện được trích và dự đoán của model. Mã Cloud giữ nhãn **Đã kiểm tra cú pháp** khi có bản đề xuất. Hai lượt gọi có thể dùng nhiều token hơn một lượt.

### Google Gemini

1. Đăng nhập [Google AI Studio](https://aistudio.google.com/apikey).
2. Chọn **Create API key** và chọn hoặc tạo project theo hướng dẫn.
3. Sao chép key để nhập vào IDE. Xem thêm [hướng dẫn Gemini API keys](https://ai.google.dev/gemini-api/docs/api-key).

### Groq

1. Đăng nhập [Groq Console](https://console.groq.com/).
2. Vào trang [API Keys](https://console.groq.com/keys), tạo một key rồi sao chép.
3. Chọn **Groq** trong IDE. Xem thêm [Groq Quickstart](https://console.groq.com/docs/quickstart).

| Nhà cung cấp khác | Trang quản lý key |
| --- | --- |
| DeepSeek | [DeepSeek Platform](https://platform.deepseek.com/api_keys) |
| OpenRouter | [OpenRouter Keys](https://openrouter.ai/settings/keys) |
| OpenAI | [OpenAI Platform API Keys](https://platform.openai.com/api-keys) |

Có thể thử một hãng từ terminal bằng lệnh dưới đây. Key chỉ dùng cho phép thử này. Dùng ô nhập trong IDE để chạy yêu cầu Cloud.

```powershell
py -3 nhap_api_key.py --provider gemini
```

Nếu Cloud trả lỗi, kiểm tra mạng, key, quyền truy cập model và giới hạn tài khoản. Có thể đặt ID model tương thích trong `%LOCALAPPDATA%\Programs\PylanceHelper\models.json`, ví dụ `{"gemini_model":"ID_MODEL_CUA_BAN"}`. File này dùng cho tùy chọn model. Nhập key qua ô nhập của IDE hoặc terminal ở trên.

## Cập nhật, gỡ và xử lý lỗi

- **Cập nhật** bằng cách chạy lại setup từ bản mới và dùng **Reload Window**. Nếu từng dùng bản cũ trên hai IDE, cập nhật hoặc gỡ riêng cho từng IDE.
- **Gỡ cài đặt** bằng `Alt+0` hoặc [go_cai_dat.bat](go_cai_dat.bat). Nếu đã cài VSIX thủ công, mở **Extensions** để gỡ extension sau khi đã gỡ runtime. Reload các cửa sổ IDE đã nạp extension.
- **Python không được nhận diện** thì chạy `py -3 --version` hoặc `python --version`. Nếu trình cài chưa nhận đúng IDE, dùng `--check` để xem điều kiện còn thiếu.
- **Phím tắt không phản hồi** thì thử lệnh tương ứng trong **Ctrl+Shift+P** và kiểm tra **Keyboard Shortcuts**. Bản cài cũ cần reload để bỏ các phím đã nạp.
- **Tool báo thiếu dữ liệu hoặc vượt giới hạn** thì xem chẩn đoán và thu nhỏ bài thử. Với ca có nhiều điều kiện, kiểm tra rằng từng điều kiện đều xuất hiện trong yêu cầu có cấu trúc.

Xem [mã bộ xử lý](core_engine), [extension](shells/vscode_ext) và [kiểm thử](tests).
