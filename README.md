# Pylance Indent Helper

Tiện ích Python trên Windows để tạo code từ yêu cầu, thử chạy và hỗ trợ sửa lỗi ngay trong VS Code hoặc Antigravity. Có chế độ offline dùng kho mẫu và chế độ gọi AI qua API. Với IDLE / Notepad++, chương trình nền cung cấp bộ phím tắt riêng.

## 1. Cài đặt lần đầu

### Chuẩn bị

- Windows, Python **3.10 trở lên** và VS Code hoặc Antigravity.
- Khi cài Python từ [python.org](https://www.python.org/downloads/windows/), bật **Add Python to PATH**.
- Internet và API key chỉ cần cho chế độ Cloud. Bạn có thể dùng `Alt+1` khi chưa có key.

Mở PowerShell để kiểm tra:

```powershell
python --version
```

### Tải và cài

**Có Git:**

```powershell
git clone https://github.com/gmaanx/pylance-indent-helper.git
cd pylance-indent-helper
```

**Không có Git:** trên trang repo, chọn **Code → Download ZIP**, giải nén, rồi mở PowerShell trong thư mục có `setup.py`.

Cài các thư viện vào Python bạn sẽ dùng. Repo có sẵn wheel để cài không cần tải thêm:

```powershell
python -m pip install --no-index --find-links .\setup_lab\wheels simpleai miniKanren sympy
```

Nếu dùng môi trường ảo, hãy dùng Python trong môi trường đó cho cả bước cài thư viện và bước chạy setup. Trình cài ưu tiên môi trường `.venv` nằm cạnh thư mục repo nếu có.

Tiếp theo, nhấp đúp [setup_nhanh.bat](setup_nhanh.bat), hoặc chạy:

```powershell
python setup.py
```

Trong **từng cửa sổ VS Code / Antigravity đang mở**, bấm **Ctrl+Shift+P → Reload Window → Enter**. Mở một file `.py` để thử phím tắt.

Trình cài chép bộ xử lý vào `%LOCALAPPDATA%\Programs\PylanceHelper`, cài extension cho cả hai IDE và khởi chạy chương trình nền. Giữ thư mục repo ở vị trí đã cài vì liên kết thư viện offline có thể trỏ về `setup_lab/offline_pkgs`. Nếu chuyển thư mục, chạy setup lại.

## 2. Sử dụng hằng ngày

1. Mở file `.py` và lưu bản sao nếu file đang có nội dung cần giữ.
2. Viết yêu cầu bằng comment `#` hoặc chuỗi ba dấu nháy. Không cần bôi đen để xử lý cả file.
3. Chọn phím tắt ở bảng bên dưới. Kết quả sẽ thay thế nội dung file; có thể dùng **Ctrl+Z** để hoàn tác trong IDE.

Ví dụ thử offline:

```python
# Giải bài toán đong nước bằng BFS với 3 bình có dung tích (3, 5, 8).
# Trạng thái ban đầu (0, 0, 8). Mục tiêu có một bình chứa 4 lít.
```

Hoặc:

```python
"""
Giải bài toán 8-puzzle bằng A*.
Trạng thái đầu: ((1, 2, 3), (4, 0, 6), (7, 5, 8)).
Trạng thái đích: ((1, 2, 3), (4, 5, 6), (7, 8, 0)).
"""
```

### Phím tắt

| Tác vụ | VS Code / Antigravity | IDLE / Notepad++ qua chương trình nền | Hoạt động |
| --- | --- | --- | --- |
| Tạo code offline | `Alt+1` | `Ctrl+Alt+1` | Chọn mẫu phù hợp và điền dữ liệu từ yêu cầu; không gọi API. |
| Tạo code bằng AI | `Alt+2` | `Ctrl+Alt+2` | Thử Cloud, sau đó LLM local nếu có, rồi kho mẫu offline. Có chạy thử và hỗ trợ sửa lỗi. |
| Gõ kết quả từng ký tự | `Alt+3` | `Ctrl+Alt+3` | Tạo code rồi gõ dần vào trình soạn thảo. Nhấn `Esc` để dừng gõ. |
| Sửa code lỗi | `Alt+4` | `Ctrl+Alt+4` | Đọc code hiện tại, thử chạy và tìm cách sửa. |
| Gỡ cài đặt | `Alt+0` | `Ctrl+Alt+0` | Dừng công cụ và gỡ các thành phần đã cài. |

`Alt+Shift+Delete` cũng là phím gỡ cài đặt. Khi chương trình nền đang chạy, `Alt+Shift+Backspace` là một phím gỡ bổ sung.

**Chọn chế độ:** dùng `Alt+1` cho bài gần các mẫu có sẵn; dùng `Alt+2` khi muốn thử AI với yêu cầu khác. Thời gian xử lý phụ thuộc bài toán, máy, mạng và nhà cung cấp API.

Kết quả có dòng trạng thái đầu file. Các nhãn `tier1_gemini`, `tier1_groq`… cho biết đã dùng Cloud; `tier3_offline(...)` cho biết đã dùng kho mẫu. `Verified` phản ánh kết quả kiểm tra thực thi của công cụ; bạn vẫn cần đối chiếu thuật toán, số liệu và kết quả với yêu cầu bài toán.

## 3. Lấy API key

Bạn chỉ cần key của **một** nhà cung cấp. Có thể cấu hình nhiều hãng; công cụ thử theo thứ tự **Gemini → Groq → DeepSeek → OpenRouter → OpenAI**, bỏ qua hãng chưa có key hoặc gọi không thành công.

### Google Gemini

1. Mở [trang API key của Google AI Studio](https://aistudio.google.com/apikey) và đăng nhập tài khoản Google.
2. Hoàn tất bước chấp nhận điều khoản nếu được hỏi.
3. Chọn **Create API key**, rồi chọn hoặc tạo Google Cloud project theo hướng dẫn trên trang.
4. Sao chép key và chuyển đến phần **Nạp key vào công cụ** bên dưới.

Nếu không chọn được project, xem phần thiết lập project hoặc nhập project trong AI Studio. Nếu không có quyền tạo key, cần tài khoản hoặc project mà bạn có quyền sử dụng. Hướng dẫn chính thức: [Using Gemini API keys](https://ai.google.dev/gemini-api/docs/api-key).

### Groq

1. Mở [Groq Console](https://console.groq.com/) và đăng nhập hoặc tạo tài khoản.
2. Vào [API Keys](https://console.groq.com/keys).
3. Chọn **Create API Key**, đặt tên dễ nhận biết, ví dụ `pylance-helper`.
4. Sao chép key vừa tạo và lưu để nạp vào công cụ.

Hướng dẫn chính thức: [Groq Quickstart](https://console.groq.com/docs/quickstart).

### Nhà cung cấp khác

| Nhà cung cấp | Trang tạo / quản lý key | Tham số nạp |
| --- | --- | --- |
| DeepSeek | [DeepSeek Platform](https://platform.deepseek.com/api_keys) | `--deepseek` |
| OpenRouter | [OpenRouter Keys](https://openrouter.ai/settings/keys) | `--openrouter` |
| OpenAI | [OpenAI Platform API Keys](https://platform.openai.com/api-keys) | `--openai` |

Đăng nhập nhà cung cấp, tạo key trong mục API Keys và kiểm tra quyền truy cập model, hạn mức hoặc số dư của tài khoản. Gói miễn phí và mức phí phụ thuộc nhà cung cấp, model và tài khoản; không phải key nào cũng dùng được ngay với mọi model.

## 4. Nạp key vào công cụ

### Cách dễ nhất: mở file nhập key

Sau khi cài đặt, nhấp đúp [nhap_api_key.bat](nhap_api_key.bat), hoặc chạy:

```powershell
python nhap_api_key.py
```

- Dán key vào dòng tương ứng với hãng bạn chọn.
- Nhấn **Enter** để bỏ qua và giữ cấu hình cũ của hãng không dùng.
- Script sẽ thử gọi Cloud nếu có key. Dòng `[THÀNH CÔNG]` kèm tên hãng và phản hồi `API_OK` giúp kiểm tra đường gọi API. Nếu đã cấu hình nhiều hãng, phép thử xác nhận hãng đầu tiên trả lời thành công.
- Nếu hiện `[CHƯA KẾT NỐI ĐƯỢC TẦNG 1]`, kiểm tra key, mạng, quyền model, hạn mức và số dư. `Alt+1` vẫn dùng được offline.

**Sau khi đổi key**, thử lại `Alt+2` trong VS Code / Antigravity. Nếu dùng IDLE / Notepad++, chạy lại `setup_nhanh.bat` để chương trình nền nạp cấu hình mới, rồi **Reload Window** nếu IDE cũng đang mở.

### Nạp bằng lệnh

Thay nội dung `YOUR_..._API_KEY` bằng key của bạn:

```powershell
python nhap_api_key.py --gemini "YOUR_GEMINI_API_KEY"
python nhap_api_key.py --groq "YOUR_GROQ_API_KEY"
```

Có thể nạp nhiều hãng trong một lần:

```powershell
python nhap_api_key.py --gemini "YOUR_GEMINI_API_KEY" --groq "YOUR_GROQ_API_KEY"
```

Kiểm tra lại kết nối với cấu hình đã lưu:

```powershell
python nhap_api_key.py --test
```

### Đổi cấu hình trong trình soạn thảo

Trong một file tạm riêng, nhập dòng sau rồi bấm `Alt+1`:

```python
# @cfg gemini:YOUR_GEMINI_API_KEY groq:YOUR_GROQ_API_KEY
```

Chỉ giữ hãng bạn cần. Dòng `# Pylance config updated: ...` cho biết đã lưu cấu hình; đây chưa phải phép thử gọi API. Dùng lệnh `--test` ở trên để thử kết nối.

Nếu model mặc định của Gemini hoặc Groq không còn khả dụng, có thể đổi model bằng cú pháp sau rồi bấm `Alt+1`:

```python
# @cfg gemini_model:MODEL_ID_TU_GOOGLE_AI_STUDIO
# @cfg groq_model:MODEL_ID_TU_GROQ_CONSOLE
```

Dùng ID model mà tài khoản của bạn được phép gọi. Thực hiện từng dòng trong file tạm riêng.

### Lưu trữ key

Cấu hình được lưu trong `core_engine/.pylance_cache.json` và bản cấu hình ở `%LOCALAPPDATA%\Programs\PylanceHelper`. Key được làm rối bằng XOR + Base64 và có thể khôi phục; người có quyền đọc file vẫn có thể lấy key.

`.gitignore` đã loại các file cấu hình này khỏi Git. Không đưa key thật vào file ví dụ, README hay commit. Lệnh có key có thể lưu trong lịch sử terminal; cách nhập trực tiếp bằng `nhap_api_key.bat` giúp tránh đặt key trong câu lệnh. Nếu đã công khai key, thu hồi tại trang quản lý của hãng và tạo key mới.

## 5. Gỡ cài đặt và cập nhật

### Gỡ cài đặt

Chọn một cách:

- Trong VS Code / Antigravity: bấm `Alt+0`.
- Với chương trình nền: bấm `Ctrl+Alt+0`.
- Nhấp đúp [go_cai_dat.bat](go_cai_dat.bat), hoặc chạy `python go_cai_dat.py`.

Bản đã sửa khóa các lệnh khi bắt đầu gỡ và chỉ báo thành công sau khi script gỡ hoàn tất. Nếu có lỗi, chạy `go_cai_dat.bat` để xem chi tiết rồi thử lại.

**Sau khi gỡ, chọn Ctrl+Shift+P → Reload Window trong từng cửa sổ VS Code / Antigravity đang mở**, hoặc đóng rồi mở lại IDE. Xóa thư mục extension không tự dỡ mã đã nạp trong bộ nhớ. Điều này đặc biệt cần thiết với bản cũ từng báo gỡ thành công nhưng `Alt+1` vẫn chạy.

Trình gỡ xóa bản cài, extension, liên kết thư viện, file chạy thử và Clipboard. Thư mục mã nguồn bạn tải về cùng file cấu hình key trong thư mục nguồn vẫn còn; muốn xóa cả bản nguồn thì tự xóa thư mục sau khi đã gỡ.

### Cập nhật bản mới

Nếu tải bằng Git, trong thư mục repo chạy:

```powershell
git pull --ff-only
python setup.py
```

Nếu tải bằng ZIP, tải bản ZIP mới, giải nén và chạy setup từ bản mới. Sau đó **Reload Window** trong các IDE để nạp extension vừa cập nhật.

## 6. Xử lý lỗi thường gặp

| Hiện tượng | Cách xử lý |
| --- | --- |
| `python` không được nhận diện hoặc mở Microsoft Store | Cài Python từ python.org, bật PATH, mở lại PowerShell và kiểm tra `python --version`. Nếu máy chỉ nhận lệnh `py`, có thể dùng `py -3 setup.py`. |
| `Alt+1` / `Alt+0` không phản hồi trong IDE | Chạy lại setup, chọn **Reload Window**, rồi kiểm tra mục **Keyboard Shortcuts** xem tổ hợp phím có bị lệnh khác chiếm không. Nếu cần gỡ ngay, chạy `go_cai_dat.bat`. |
| Đã gỡ nhưng `Alt+1` vẫn chạy | Reload **tất cả** cửa sổ VS Code / Antigravity. Với bản cũ, mã extension còn trong bộ nhớ dù file đã bị xóa. |
| IDLE / Notepad++ không nhận `Alt+1` | Dùng `Ctrl+Alt+1`. Chạy lại setup nếu chương trình nền chưa được khởi động. |
| Thiếu `simpleai`, `kanren` hoặc `sympy` | Chạy lại lệnh cài wheel ở phần 1 bằng đúng Python đang xử lý code. Nếu dùng `.venv`, gọi trực tiếp Python trong `.venv`. |
| Đã nạp key nhưng kết quả vẫn ghi `tier3_offline(...)` | Chạy `python nhap_api_key.py --test`; kiểm tra key, mạng, model và hạn mức. Xem tên hãng thật sự phản hồi trong kết quả kiểm tra. |
| Kết quả báo `Unverified` hoặc sai dữ liệu | Đọc lại yêu cầu và số liệu, chạy code để xem lỗi cụ thể; thử `Alt+4` với code lỗi hoặc `Alt+2` với yêu cầu rõ hơn. |
| Code bị thay thế ngoài ý muốn | Dùng **Ctrl+Z** trong IDE và thử lại trên file riêng. |

## 7. Các file cần biết

| File / thư mục | Mục đích |
| --- | --- |
| [setup_nhanh.bat](setup_nhanh.bat) / [setup.py](setup.py) | Cài hoặc cập nhật extension và chương trình nền. |
| [nhap_api_key.bat](nhap_api_key.bat) / [nhap_api_key.py](nhap_api_key.py) | Nhập key và thử kết nối Cloud. |
| [go_cai_dat.bat](go_cai_dat.bat) / [go_cai_dat.py](go_cai_dat.py) | Gỡ cài đặt và hiển thị lỗi nếu chưa hoàn tất. |
| [core_engine](core_engine) | Phân tích yêu cầu, chọn mẫu / gọi AI và kiểm tra code. |
| [shells](shells) | Extension cho IDE và chương trình nền Windows. |
| [setup_lab/wheels](setup_lab/wheels) | Các gói Python để cài offline. |
| [tests](tests) | Kiểm thử bộ xử lý và luồng gỡ cài đặt. |
