# Trợ lý bài tập Python

Tiện ích Windows hỗ trợ luyện bài Python trong VS Code hoặc Antigravity. Bộ giải offline hỗ trợ 49 dạng bài có đặc tả. Dùng **Alt+1** cho bài có bộ giải, **Alt+3** để gửi đề tới API Cloud hoặc **Alt+5** để dùng Ollama trên máy. Trong bài thi, dùng các chế độ mà quy chế cho phép.

- [Cài đặt trên Windows](#cài-đặt-offline)
- [Thử một bài và chạy mã](#dùng-trong-ide)
- [Bộ giải offline và ví dụ](#dùng-bộ-giải-offline)
- [Lấy key và dùng API Cloud](#dùng-api-cloud-trong-ide-với-alt3)
- [Cài Ollama và dùng AI cục bộ](#cài-và-dùng-ai-cục-bộ-với-alt5)
- [Cập nhật, gỡ và xử lý lỗi](#cập-nhật-gỡ-và-xử-lý-lỗi)

## Cài đặt offline

1. Chuẩn bị Python 3.10 trở lên và VS Code hoặc Antigravity. Nếu vừa cài Python, mở lại PowerShell và kiểm tra bằng `py -3 --version` hoặc `python --version`. [Tải Python cho Windows](https://www.python.org/downloads/windows/)
2. Giải nén gói cài Windows vào một thư mục có thể ghi. Nếu tải mã nguồn từ GitHub, chọn **Code → Download ZIP** rồi giải nén, hoặc dùng `git clone https://github.com/gmaanx/pylance-indent-helper.git`. Gói cài mang sẵn wheel cần thiết cho Offline.
3. Nhấp đúp **setup_nhanh.bat**, hoặc mở PowerShell ngay trong thư mục chứa file và chạy lệnh bên dưới. [setup_nhanh.bat](setup_nhanh.bat)
4. Khi cài xong, bấm **Ctrl+Shift+P → Reload Window** trong IDE đang mở để nạp extension. Nếu IDE đang đóng, mở nó sau khi cài.

```powershell
.\setup_nhanh.bat
```

Trình cài chọn một IDE có CLI, tạo môi trường Python riêng và chạy thử một bài SimpleAI. Có thể dùng `py -3 setup.py` hoặc `python setup.py` nếu muốn gọi trực tiếp. Các lệnh sau kiểm tra điều kiện hoặc chỉ định IDE.

```powershell
.\setup_nhanh.bat --check
.\setup_nhanh.bat --ide vscode
.\setup_nhanh.bat --ide antigravity
```

Nếu IDE không có CLI, chạy `.\setup_nhanh.bat --ide manual`. Mở **Extensions → Install from VSIX** trong IDE, chọn file VSIX mà trình cài in ra, rồi tải lại cửa sổ.

Gói mặc định chỉ kèm SimpleAI. Nếu cần chạy các mẫu cũ có `import kanren` hoặc `import sympy`, tạo gói với `py -3 setup_lab/build_release.py --full` và cài bằng `setup_nhanh.bat --profile full`. Lệnh `py -3 setup_lab/build_release.py` tạo gói mặc định. Cả hai ZIP nằm trong `dist/`.

Khi file cần SimpleAI mà Python đang chọn báo `ModuleNotFoundError`, lưu file rồi bấm **Ctrl+Shift+P** và chọn **Bài tập Python: Chạy file đã lưu bằng Python của công cụ**. Lệnh này chạy bằng môi trường đã cài thư viện và hiện kết quả trong Terminal. Muốn dùng nút Run của Python extension, mở **Bài tập Python: Xem môi trường Python của công cụ**, sao chép đường dẫn và chọn đường dẫn đó bằng **Python: Select Interpreter**.

## Dùng trong IDE

1. Mở file `.py`, đặt đề trong dấu ba nháy `"""` rồi đặt con trỏ trong khối đề. Dùng cách này cho **Alt+1** đến **Alt+5**. Có thể bôi đen một đề để chỉ định vùng cần xử lý.
2. Bấm **Alt+1** và kiểm tra cửa sổ so sánh. Ví dụ dưới đây tìm ba số nguyên tố đầu tiên.
3. Chọn **Áp dụng** ở thông báo của IDE để cập nhật file. Nếu file hoặc vùng chọn đã thay đổi, chạy lại lệnh để tạo bản xem trước mới.
4. Lưu bằng **Ctrl+S**. Nếu mã có đoạn chạy thử, chọn **Bài tập Python: Chạy file đã lưu bằng Python của công cụ** trong **Ctrl+Shift+P** để xem kết quả ở Terminal. Nếu mã chỉ định nghĩa lớp hoặc hàm, cần gọi lớp hoặc hàm để thấy kết quả.

```python
"""
Liệt kê 3 số nguyên tố đầu tiên.
"""
```

Nếu file có nhiều đề, chọn từng khối bằng con trỏ hoặc vùng bôi đen. Khi áp dụng, công cụ thay đúng khối đang giải. Hai đề 8-puzzle và phân ca trực có thể thử trực tiếp từ file mẫu. [thu_nghiem.py](thu_nghiem.py)

| Phím | Lệnh |
| --- | --- |
| `Alt+1` | Giải offline từ yêu cầu hoặc dữ liệu có cấu trúc |
| `Alt+2` | Phân tích offline |
| `Alt+3` | Dùng API Cloud với key nhập trong phiên IDE |
| `Alt+4` | Xem đề xuất sửa code offline |
| `Alt+5` | Dùng model Ollama đã tải trên máy |
| `Alt+0` | Mở xác nhận gỡ công cụ |

Có thể tìm các lệnh trong **Ctrl+Shift+P**. Lệnh hủy hiện ở thông báo tiến độ khi đang xử lý. Bản cài dành cho IDE và các phím tạo code hoạt động khi đang soạn Python.

## Dùng bộ giải offline

Bộ giải offline xử lý các dạng mà nó đọc được đầy đủ dữ kiện và ràng buộc. `@solve` là định dạng tùy chọn để khai báo dữ liệu chính xác. Với đề tự do chưa có bộ giải phù hợp, chọn **Alt+3** hoặc **Alt+5** ngay trên cùng khối văn bản.

Offline chỉ mở bản xem trước khi nhận diện được đặc tả hoặc khi bạn gọi đích danh mẫu tham khảo. Khi đề có điều kiện chưa hỗ trợ, tool giữ nguyên file và hiển thị chẩn đoán. Hai ví dụ lớp Python được kiểm thử từ ảnh báo lỗi dùng thư viện chuẩn.

```python
# @solve {"type":"vector24"}
# @solve {"type":"diem3d"}
```

Lớp `Vector24` nhận 24 tọa độ, hỗ trợ phép cộng, `tich_vo_huong()` và `goc()` theo radian. Ví dụ `Vector24([1] * 24).tich_vo_huong(Vector24([2] * 24))` trả `48`.

Xem bảng đối chiếu bài tập theo từng buổi và ví dụ dùng SimpleAI. [Phạm vi offline theo môn học](docs/course-coverage.md)

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

## Dùng API Cloud trong IDE với Alt+3

1. Lấy API key từ nhà cung cấp theo một trong các hướng dẫn bên dưới.
2. Mở file Python, nhập đề dưới dạng comment hoặc chọn đúng vùng cần xử lý.
3. Bấm **Alt+3** hoặc chọn **Bài tập Python: Gửi yêu cầu đến Cloud** trong Command Palette. Chọn hãng, nhập key rồi xác nhận gửi vùng chọn hoặc toàn bộ file.
4. Kiểm tra cửa sổ so sánh và chẩn đoán. Chỉ bấm **Áp dụng** khi kết quả phù hợp.

Key được giữ trong bộ nhớ phiên IDE. Dùng **Quên API key phiên này** để xóa. File cấu hình key kiểu cũ có thể vẫn nằm trong bản nguồn bạn từng dùng.

Để thử luồng API, tạo file Python mới, dán dòng sau và bấm **Alt+3**. Cùng một đề cũng có thể dùng để thử **Alt+5**.

```python
# Viết hàm chuan_hoa_ten(text) trả chuỗi đã bỏ khoảng trắng hai đầu và gộp các khoảng trắng liên tiếp thành một dấu cách. Thêm ví dụ với "  An   Bình  ".
```

Nếu đề đã khớp một bộ giải offline, công cụ có thể trả kết quả ngay sau khi xác nhận chế độ. Dòng trạng thái ghi nguồn kết quả.

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

## Cài và dùng AI cục bộ với Alt+5

Mở PowerShell tại thư mục đã giải nén và chạy:

```powershell
.\setup_nhanh.bat --local
```

Lựa chọn này dùng Ollama đã cài hoặc cài Ollama cho tài khoản hiện tại qua WinGet, rồi tải `qwen2.5-coder:1.5b` nếu máy chưa có. Bước cài đầu cần mạng. Model khoảng 986 MB và Ollama cần thêm dung lượng cho ứng dụng. Sau khi tải xong, mở Ollama, reload IDE rồi bấm **Alt+5**. [Cài Ollama trên Windows](https://docs.ollama.com/windows) · [Dung lượng model mặc định](https://ollama.com/library/qwen2.5-coder:1.5b)

Có thể chọn model khác đã tải được trên máy bằng `.\setup_nhanh.bat --local --local-model TÊN_MODEL`. Nếu thiếu WinGet, cài Ollama từ trang chính thức rồi chạy lại lệnh. Nếu Ollama chưa chạy, mở ứng dụng trước khi bấm **Alt+5**. Công cụ ưu tiên bộ giải có đặc tả trước khi hỏi model. Bản nháp từ model cục bộ được kiểm tra cú pháp và cần đối chiếu với đề.

Luồng cục bộ chỉ gửi nội dung tới Ollama ở `127.0.0.1:11434`. Khi ứng dụng đang chạy, có thể dùng `ollama list` để xem model đã tải. Dùng `.\setup_nhanh.bat --check --local` để kiểm tra điều kiện cài. Nếu bước tải model lỗi, phần Offline vẫn dùng được và bạn có thể chạy lại lệnh `--local` sau.

## Cập nhật, gỡ và xử lý lỗi

Cập nhật bằng cách chạy lại setup từ bản mới rồi chọn **Reload Window**. Nếu dùng Git, chạy `git pull --ff-only` trước khi chạy setup. Nếu dùng profile đầy đủ, thêm `--profile full` khi nâng cấp. Nếu đã cài ở hai IDE, cập nhật cho từng IDE.

Gỡ bằng **Alt+0** hoặc chạy **go_cai_dat.bat**. Nếu cài VSIX thủ công, gỡ thêm extension trong **Extensions**, rồi tải lại các cửa sổ IDE. Ollama và model do ứng dụng Ollama quản lý riêng. [go_cai_dat.bat](go_cai_dat.bat)

| Hiện tượng | Cách xử lý |
| --- | --- |
| `python` không được nhận diện | Kiểm tra `py -3 --version` hoặc `python --version`. Nếu chưa có Python phù hợp, cài Python 3.10 trở lên và mở lại terminal. |
| Trình cài không thấy IDE | Chạy `.\setup_nhanh.bat --check`. Nếu IDE thiếu CLI, cài theo chế độ `--ide manual`. |
| Phím tắt không phản hồi | Mở file `.py`, tải lại cửa sổ và thử lệnh qua **Ctrl+Shift+P**. Kiểm tra **Keyboard Shortcuts** nếu phím bị trùng. |
| `SyntaxError` xuất hiện ở dòng đề bài | Đặt đề sau dấu `#`. Dùng phím của công cụ để tạo bản xem trước trước khi chạy file Python. |
| `ModuleNotFoundError: No module named 'simpleai'` | Lưu file và chọn **Chạy file đã lưu bằng Python của công cụ**. Với `kanren` hoặc `sympy`, dùng gói đầy đủ và profile `full`. |
| Offline báo thiếu dữ liệu hoặc ngoài phạm vi | Đối chiếu kiểu `@solve`, dữ liệu và ràng buộc hoặc thử **Alt+5** hay **Alt+3** cho câu hỏi tự do. |
| API báo `401`, `403` hoặc `429` | Kiểm tra key, quyền truy cập model hoặc hạn mức của hãng. Dùng lệnh **Quên API key phiên này** để nhập key mới. |
| Ollama không kết nối được hoặc thiếu model | Mở Ollama, kiểm tra `ollama list`, sau đó chạy lại `.\setup_nhanh.bat --local` nếu cần tải model. |

Xem [mã bộ xử lý](core_engine), [extension](shells/vscode_ext) và [kiểm thử](tests).
