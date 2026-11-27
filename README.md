# Trợ lý bài tập Python

Tiện ích Windows hỗ trợ luyện bài Python trong VS Code hoặc Antigravity. Bộ giải offline hỗ trợ 49 dạng bài có đặc tả. Dùng **Alt+1** cho bài có bộ giải, **Alt+3** để gửi đề tới API Cloud hoặc **Alt+5** để dùng Ollama trên máy. Trong bài thi, dùng các chế độ mà quy chế cho phép.

- [Cài đặt trên Windows](#cài-đặt-offline)
- [Thử một bài và chạy mã](#dùng-trong-ide)
- [Bộ giải offline và ví dụ](#dùng-bộ-giải-offline)
- [Lấy key và dùng API Cloud](#dùng-api-cloud-trong-ide-với-alt3)
- [Cài Ollama và dùng AI cục bộ](#cài-và-dùng-ai-cục-bộ-với-alt5)
- [Cập nhật, gỡ và xử lý lỗi](#cập-nhật-gỡ-và-xử-lý-lỗi)

## Cài đặt offline

1. Tương thích từ **Python 3.8 đến Python 3.13** trên Windows (kể cả máy phòng Lab chạy Python 3.8/3.9 hoặc Anaconda) cùng VS Code hoặc Antigravity. Kiểm tra nhanh bằng `py -3 --version` hoặc `python --version`. [Tải Python cho Windows](https://www.python.org/downloads/windows/)
2. Giải nén gói cài Windows vào một thư mục có thể ghi, hoặc kéo từ GitHub đầu giờ bằng `git clone https://github.com/gmaanx/pylance-indent-helper.git`. Gói cài đã kèm sẵn trọn bộ wheel offline (`simpleai`, `miniKanren`, `sympy`, `toolz`).
3. **Cách cài đặt nhanh đầu giờ:**
   - **Cài trọn gói 1 chạm cho Phòng Thi** (Full thư viện + Extension IDE + tự chọn model Ollama `3B`/`1.5B` theo RAM máy + nạp sẵn API Key mã hóa chạy ngầm không popup):
     ```powershell
     .\setup_phong_thi.bat --provider gemini --key AIzaSy...
     ```
     *(Nếu không truyền `--provider`/`--key`, script vẫn cài đầy đủ Offline + Extension + Ollama theo RAM).*
   - Hoặc chỉ cài **Offline + API Cloud** siêu nhanh (< 10 giây, mặc định cài đủ `simpleai` + `miniKanren` + `sympy`): nhấp đúp [setup_nhanh.bat](setup_nhanh.bat).
4. Khi cài xong, bấm **Ctrl+Shift+P → Reload Window** trong IDE đang mở để nạp extension (`v1.8.0`). Trình cài tự động cài đặt đồng thời cho cả **VS Code** và **Antigravity** (nếu máy có cả hai).

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

1. Hỗ trợ đủ **3 hình thức làm bài**: file `.py` trống (đặt đề trong `""" ... """` hoặc `# ...`), file `.py` khung có sẵn của giảng viên (`# TODO` / `pass` / `NotImplementedError` — giữ nguyên tên lớp/hàm), và **trực tiếp trong ô code Jupyter Notebook (`.ipynb`)**. Công cụ tự động đọc mẫu cấu trúc các file dữ liệu `.txt`, `.json`, `.csv` và module `.py` nằm cùng thư mục để viết code khớp dữ liệu ngay lần đầu.
2. Đặt con trỏ vào khối đề rồi bấm **`Alt+2` (Auto-Pilot — khuyên dùng chính)**. Công cụ tự động chọn tầng mạnh nhất đang hoạt động (**Offline chuẩn → Cloud API chạy ngầm nếu còn mạng → Ollama cục bộ nếu mất mạng → Phôi Vàng BM25**), kèm 55 Phôi Vàng Chương 1–9 và tự chạy kiểm thử ngầm (`Shadow Run`) để bắt `Traceback` sửa lỗi trước khi chèn code sạch 100% (không chèn bất kỳ dòng comment đánh dấu nào của tool, không bật thông báo nổi dễ lộ).
3. Bấm **`Alt+6`** để tự động lưu và chạy ngay file `.py` (hoặc chạy ô Notebook hiện tại) bằng đúng Python đã cài sẵn `simpleai`, `miniKanren`, `sympy` của công cụ. Cả 3 chế độ (**Offline**, **Cloud**, **Ollama**) đều tự sinh `def main():` + `if __name__ == "__main__": main()` gọi lời giải và in kết quả theo đúng định dạng đề bài.

```python
"""
Liệt kê 3 số nguyên tố đầu tiên.
"""
```

Nếu file có nhiều đề, chọn từng khối bằng con trỏ hoặc vùng bôi đen. Công cụ thay đúng khối đang giải. Các đề mẫu 8-Puzzle, phân ca trực CSP và lớp `NutTimKiem` có sẵn trong [thu_nghiem.py](thu_nghiem.py).

| Phím | Lệnh |
| --- | --- |
| `Alt+1` | Giải nhanh Offline chính xác (`< 0.1s`, 0% mạng) |
| `Alt+2` | **Auto-Pilot 1 chạm** (Offline → Cloud ngầm → Ollama → Phôi Vàng BM25 + tự chạy ngầm sửa lỗi) |
| `Alt+3` | Dùng API Cloud (chạy thẳng không popup nếu đã lưu key qua `nhap_api_key.bat`) |
| `Alt+4` | **True Self-Fix**: chạy thử bắt `SyntaxError` / `Traceback` thực tế và tự vá code |
| `Alt+5` | Dùng model Ollama trên máy (kèm Phôi Vàng BM25 + tự chạy ngầm sửa lỗi) |
| `Alt+6` | Tự lưu & chạy ngay file `.py` / ô `.ipynb` bằng Python của công cụ |
| `Alt+0` | Mở xác nhận gỡ toàn bộ công cụ (`Alt+1–6`, Extension IDE & Ollama) |

Có thể tìm các lệnh trong **Ctrl+Shift+P**. Lệnh hủy hiện ở thông báo tiến độ khi đang xử lý. Bản cài dành cho IDE và các phím tạo code hoạt động khi đang soạn Python.

## Dùng bộ giải offline

Bộ giải offline xử lý các dạng mà nó đọc được đầy đủ dữ kiện và ràng buộc. `@solve` là định dạng tùy chọn để khai báo dữ liệu chính xác. Với đề tự do chưa có bộ giải phù hợp, chọn **Alt+3** hoặc **Alt+5** ngay trên cùng khối văn bản.

Chế độ offline đưa ra đề xuất khi nhận diện được đặc tả hoặc khi bạn gọi đích danh mẫu tham khảo. Khi đề có điều kiện chưa hỗ trợ, IDE hiển thị chẩn đoán. Hai ví dụ lớp Python được kiểm thử từ ảnh báo lỗi dùng thư viện chuẩn.

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

Mỗi dòng `@solve` là một ví dụ độc lập. Bôi đen một dòng trước khi bấm `Alt+1`. Bộ giải cũng nhận một số câu tiếng Việt về đong nước, đổi tiền, 8-puzzle, minimax, Fibonacci, số nguyên tố, tổng chẵn/lẻ, N hậu và `Diem3D`/`Vector24` khi nhận diện được toàn bộ nội dung. Có thể yêu cầu định dạng in ngay cuối câu tiếng Việt (như `in dạng JSON`, `mỗi số trên một dòng`, `cách nhau bởi dấu phẩy`, `làm tròn 2 chữ số thập phân`, `theo định dạng "Kết quả: {result}"`) hoặc thêm trường `"output"` trong `@solve` (`format`: `json`, `pretty_json`, `lines`, `join`, `fixed`, `template`; tùy chọn `sep`, `decimals`, `prefix`, `suffix`, `field`, `none_text`).

**Đã giải theo đặc tả** nghĩa là bộ giải offline đã tính kết quả theo dữ liệu và quy tắc được hỗ trợ. Bài vượt giới hạn, có dữ liệu thiếu hoặc dùng ràng buộc chưa hỗ trợ sẽ có thông báo riêng. Mẫu tham khảo và đề xuất Cloud cần được đối chiếu với đề. **Đã kiểm tra cú pháp** xác nhận Python đọc được đoạn code.

## Dùng API Cloud trong IDE với Alt+3

1. Lấy API key từ nhà cung cấp theo một trong các hướng dẫn bên dưới.
2. Mở file Python, nhập đề dưới dạng comment hoặc chọn đúng vùng cần xử lý.
3. Bấm **Alt+3** hoặc chọn **Bài tập Python: Gửi yêu cầu đến Cloud** trong Command Palette. Chọn hãng, nhập key rồi xác nhận gửi vùng chọn hoặc toàn bộ file.
4. Đối chiếu mã được chèn trong file với yêu cầu. Dùng **Ctrl+Z** để hoàn tác khi cần.

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

Kiểm tra và lưu sẵn API key đã mã hóa (XOR + Base64) từ terminal trước giờ thi để bấm **Alt+2** hoặc **Alt+3** chạy ngầm hoàn toàn không hiện popup:

```powershell
.\nhap_api_key.bat --provider gemini --key AIzaSy...
# Xóa key đã lưu bất kỳ lúc nào (hoặc bấm Alt+0 gỡ toàn bộ):
.\nhap_api_key.bat --clear
```

Nếu Cloud trả lỗi, kiểm tra mạng, key, quyền truy cập model và giới hạn tài khoản. Có thể đặt ID model tương thích trong `%LOCALAPPDATA%\Programs\PylanceHelper\models.json`, ví dụ `{"gemini_model":"ID_MODEL_CUA_BAN"}`. File này dùng cho tùy chọn model. Nhập key qua ô nhập của IDE hoặc terminal ở trên.

## Cài và dùng AI cục bộ với Alt+5

Mở PowerShell tại thư mục đã giải nén và chạy:

```powershell
.\setup_ollama.bat
```

`setup_ollama.bat` có thể chạy riêng. Nó dùng ứng dụng Ollama sẵn có hoặc cài Ollama cho tài khoản hiện tại qua WinGet, rồi tải `qwen2.5-coder:1.5b` nếu cần. Lần tải đầu cần mạng. Model khoảng 986 MB và Ollama cần thêm dung lượng cho ứng dụng. Sau khi tải xong, mở Ollama, tải lại cửa sổ IDE rồi bấm **Alt+5**. [Cài Ollama trên Windows](https://docs.ollama.com/windows) · [Dung lượng model mặc định](https://ollama.com/library/qwen2.5-coder:1.5b)

Có thể chọn model khác bằng `.\setup_ollama.bat --local-model TÊN_MODEL`. Nếu thiếu WinGet, cài Ollama từ trang chính thức rồi chạy lại lệnh. **Alt+5** gửi đề tới model chạy trên máy tại `127.0.0.1:11434`, kể cả khi bài có bộ giải offline. Tiện ích kiểm tra cú pháp của mã trả về.

Dùng `.\setup_ollama.bat --check` để kiểm tra model. Chạy lại `.\setup_ollama.bat` nếu tải model bị gián đoạn.

## Cập nhật, gỡ và xử lý lỗi

Cập nhật bằng cách chạy lại setup từ bản mới rồi chọn **Reload Window**. Nếu dùng Git, chạy `git pull --ff-only` trước khi chạy setup. Nếu dùng profile đầy đủ, thêm `--profile full` khi nâng cấp. Nếu đã cài ở hai IDE, cập nhật cho từng IDE.

| Thành phần | Cài đặt | Gỡ trong terminal | Gỡ khi nhấp đúp |
| --- | --- | --- | --- |
| Offline + API | [setup_nhanh.bat](setup_nhanh.bat) | [go_cai_dat.bat](go_cai_dat.bat) | [go_cai_dat.vbs](go_cai_dat.vbs) |
| Ollama | [setup_ollama.bat](setup_ollama.bat) | [go_ollama.bat](go_ollama.bat) | [go_ollama.vbs](go_ollama.vbs) |

File `.vbs` chạy lệnh gỡ ở nền khi nhấp đúp. **Alt+0** (và `go_cai_dat.bat` không tham số) thực hiện **xóa sạch dấu vết 100%**: gỡ toàn bộ `Alt+1` đến `Alt+6`, xóa Extension khỏi cả VS Code và Antigravity, dừng toàn bộ tiến trình Ollama, chạy uninstaller ngầm và xóa triệt để `Programs\Ollama`, `%LOCALAPPDATA%\Ollama`, `~/.ollama`, `PylanceHelper`, `PylanceHelperLocalAI`, `PylanceHelperLogs`, shortcut Start Menu/Startup cùng khóa Registry `Run`/`Path`, sau đó **tự động `Reload Window`** để xóa sạch phím tắt khỏi bộ nhớ IDE ngay lập tức. `go_ollama.bat` dùng khi chỉ muốn gỡ nhẹ riêng cấu hình Ollama.

| Hiện tượng | Cách xử lý |
| --- | --- |
| `python` không được nhận diện | Kiểm tra `py -3 --version` hoặc `python --version`. Nếu chưa có Python phù hợp, cài Python 3.10 trở lên và mở lại terminal. |
| Trình cài không thấy IDE | Chạy `.\setup_nhanh.bat --check`. Nếu IDE thiếu CLI, cài theo chế độ `--ide manual`. |
| Phím tắt không phản hồi | Mở file `.py`, tải lại cửa sổ và thử lệnh qua **Ctrl+Shift+P**. Kiểm tra **Keyboard Shortcuts** nếu phím bị trùng. |
| `SyntaxError` xuất hiện ở dòng đề bài | Đặt đề trong dấu ba nháy hoặc sau dấu `#`. Dùng phím của công cụ để tạo đề xuất. |
| `ModuleNotFoundError: No module named 'simpleai'` | Lưu file và chọn **Chạy file đã lưu bằng Python của công cụ**. Với `kanren` hoặc `sympy`, dùng gói đầy đủ và profile `full`. |
| Offline báo thiếu dữ liệu hoặc ngoài phạm vi | Đối chiếu kiểu `@solve`, dữ liệu và ràng buộc hoặc thử **Alt+5** hay **Alt+3** cho câu hỏi tự do. |
| API báo `401`, `403` hoặc `429` | Kiểm tra key, quyền truy cập model hoặc hạn mức của hãng. Dùng lệnh **Quên API key phiên này** để nhập key mới. |
| Ollama không kết nối được hoặc thiếu model | Mở Ollama, kiểm tra `.\setup_ollama.bat --check` hoặc chạy lại bộ cài để tải model. |

Xem [mã bộ xử lý](core_engine), [extension](shells/vscode_ext) và [kiểm thử](tests).
