const vscode = require('vscode');
const { spawn } = require('node:child_process');
const { randomUUID } = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const PREFIX = 'pylanceIndentHelper.';
const PREVIEW_SCHEME = 'python-practice-preview';
const RUNNING_CONTEXT = PREFIX + 'running';
const APPLY = 'Áp dụng';
const PYTHON_RUNTIME_INFO = 'Xem môi trường Python';
const COPY_PYTHON_PATH = 'Sao chép đường dẫn';
const RUN_SAVED_FILE = 'Chạy file đã lưu bằng Python của công cụ';
const INSTALL_MESSAGE = 'Chạy setup_nhanh.bat rồi tải lại cửa sổ để nạp bộ xử lý Python.';
const PROVIDERS = [
  { label: 'Gemini', id: 'gemini' },
  { label: 'Groq', id: 'groq' },
  { label: 'DeepSeek', id: 'deepseek' },
  { label: 'OpenRouter', id: 'openrouter' },
  { label: 'OpenAI', id: 'openai' }
];
const TASK_ENV = Object.fromEntries(
  [...PROVIDERS.map(({ id }) => id.toUpperCase() + '_API_KEY'), 'GOOGLE_API_KEY'].map((name) => [name, ''])
);
const STATUS_LABELS = {
  verified: 'Đã giải theo đặc tả',
  syntax_checked: 'Đã kiểm tra cú pháp',
  reference: 'Mẫu tham khảo',
  needs_input: 'Thiếu dữ liệu',
  unsupported: 'Ngoài phạm vi hỗ trợ',
  limit: 'Vượt giới hạn xử lý',
  invalid: 'Dữ liệu không hợp lệ',
  not_run: 'Chưa chạy',
  runtime_checked: 'Chạy được'
};

let activeOperation;
let pendingPreview;
let uninstalling = false;
let disabled = false;
const sessionCredentials = new Map();
const previewDocuments = new Map();

function getRuntime() {
  if (!process.env.LOCALAPPDATA) {
    throw new Error(INSTALL_MESSAGE);
  }
  const root = path.join(process.env.LOCALAPPDATA, 'Programs', 'PylanceHelper');
  let record;
  try {
    record = JSON.parse(fs.readFileSync(path.join(root, 'runtime.json'), 'utf8'));
  } catch {
    throw new Error(INSTALL_MESSAGE);
  }
  if (!record || typeof record.engineRoot !== 'string' || !path.isAbsolute(record.engineRoot) ||
      typeof record.python !== 'string' || !path.isAbsolute(record.python)) {
    throw new Error(INSTALL_MESSAGE);
  }
  return { ...record, root };
}

function runtimeReady(runtime) {
  return !disabled && fs.existsSync(__filename) &&
    fs.existsSync(path.join(runtime.root, 'runtime.json')) &&
    !fs.existsSync(path.join(runtime.root, '.uninstalling')) &&
    fs.existsSync(runtime.python) &&
    fs.existsSync(path.join(runtime.engineRoot, 'core_engine', 'cli_entry.py'));
}

function runProcess(executable, args, cwd, input, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new Error('Đã hủy yêu cầu.'));
      return;
    }
    const child = spawn(executable, args, {
      cwd,
      windowsHide: true,
      env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' }
    });
    let stdout = '';
    let settled = false;

    function complete(error, result) {
      if (settled) return;
      settled = true;
      signal?.removeEventListener('abort', cancel);
      if (error) reject(error);
      else resolve(result);
    }

    function cancel() {
      child.kill();
      complete(new Error('Đã hủy yêu cầu.'));
    }

    const limit = 4 * 1024 * 1024;
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', (chunk) => {
      if (settled) return;
      stdout += chunk;
      if (stdout.length > limit) {
        child.kill();
        complete(new Error('Kết quả vượt giới hạn kích thước.'));
      }
    });
    child.stderr.resume();
    child.on('error', complete);
    child.on('close', (code) => complete(null, { code, stdout }));
    child.stdin.on('error', (error) => {
      child.kill();
      complete(error);
    });
    signal?.addEventListener('abort', cancel, { once: true });
    child.stdin.end(input);
  });
}

async function chooseCredentials() {
  const provider = await vscode.window.showQuickPick(PROVIDERS, {
    title: 'Chọn nhà cung cấp Cloud',
    placeHolder: 'Chỉ nhà cung cấp đã chọn nhận yêu cầu.'
  });
  if (!provider) return null;

  const previousKey = sessionCredentials.get(provider.id);
  const key = previousKey || (await vscode.window.showInputBox({
    title: 'Nhập API key ' + provider.label,
    prompt: 'Key được giữ trong phiên IDE hiện tại.',
    password: true,
    ignoreFocusOut: true,
    validateInput: (value) => value.trim() ? undefined : 'Nhập API key để gửi yêu cầu.'
  }))?.trim();
  return key ? { provider, key } : null;
}

function takeSnapshot(editor) {
  const document = editor.document;
  const source = document.getText();
  const selection = editor.selection;
  const start = document.offsetAt(selection.start);
  const end = document.offsetAt(selection.end);
  return {
    editor, document, source, start, end,
    version: document.version,
    range: selection.isEmpty
      ? new vscode.Range(document.positionAt(0), document.positionAt(source.length))
      : new vscode.Range(selection.start, selection.end),
    replaceStart: selection.isEmpty ? 0 : start,
    replaceEnd: selection.isEmpty ? source.length : end
  };
}

function snapshotUnchanged(snapshot) {
  const { editor, document, version, start, end } = snapshot;
  return !document.isClosed && document.version === version &&
    editor.selections.length === 1 &&
    document.offsetAt(editor.selection.start) === start &&
    document.offsetAt(editor.selection.end) === end;
}

function statusLabel(response) {
  if (Object.hasOwn(STATUS_LABELS, response.validation_status)) {
    return STATUS_LABELS[response.validation_status];
  }
  return 'Chưa kiểm chứng';
}

function resultMessage(response) {
  const diagnostics = Array.isArray(response.diagnostics)
    ? response.diagnostics.filter((value) => typeof value === 'string')
    : [];
  if (typeof response.error_detail === 'string' && response.error_detail &&
      !diagnostics.includes(response.error_detail)) {
    diagnostics.unshift(response.error_detail);
  }
  const summary = typeof response.stdout_preview === 'string' ? response.stdout_preview : '';
  const details = diagnostics.filter((entry) => entry !== summary);
  return [statusLabel(response), summary, ...details].filter(Boolean).join(' · ').slice(0, 500);
}

function knownDependencies(code) {
  const dependencies = new Set();
  for (const match of code.matchAll(/^\s*(?:from\s+(\w+)(?:\.\w+)*\s+import\b|import\s+([^#\r\n]+))/gm)) {
    const modules = match[1] ? [match[1]] : match[2].split(',').map((part) => part.trim().split(/[.\s]/, 1)[0]);
    for (const name of modules) {
      if (['simpleai', 'kanren', 'sympy'].includes(name)) dependencies.add(name);
    }
  }
  return [...dependencies];
}

function runtimePackages(runtime) {
  return runtime.dependencyProfile === 'full' ? ['simpleai', 'kanren', 'sympy'] : ['simpleai'];
}

async function showPythonRuntime() {
  try {
    const runtime = getRuntime();
    if (!runtimeReady(runtime)) throw new Error(INSTALL_MESSAGE);
    const action = await vscode.window.showInformationMessage(
      'Python của công cụ đã cài ' + runtimePackages(runtime).join(', ') + '.',
      {
        modal: true,
        detail: runtime.python + '\n\nCó thể chọn đường dẫn này bằng lệnh Python: Select Interpreter, hoặc dùng lệnh "' + RUN_SAVED_FILE + '".'
      },
      COPY_PYTHON_PATH
    );
    if (action === COPY_PYTHON_PATH) await vscode.env.clipboard.writeText(runtime.python);
  } catch (error) {
    await vscode.window.showErrorMessage(error.message);
  }
}

async function runSavedFile() {
  if (uninstalling || disabled) return;
  const document = vscode.window.activeTextEditor?.document;
  const file = document?.uri.fsPath;
  if (!document || document.uri.scheme !== 'file' || document.languageId !== 'python' ||
      !path.isAbsolute(file || '') || path.extname(file).toLowerCase() !== '.py' || !fs.existsSync(file)) {
    await vscode.window.showWarningMessage('Mở file .py đã lưu để chạy bằng Python của công cụ.');
    return;
  }
  if (document.isDirty) {
    await vscode.window.showWarningMessage('Lưu các thay đổi của file .py rồi chạy lại lệnh này.');
    return;
  }
  if (!vscode.workspace.isTrusted) {
    await vscode.window.showWarningMessage('IDE đang ở Restricted Mode. Lệnh chạy file cần một workspace đáng tin cậy.');
    return;
  }

  try {
    const runtime = getRuntime();
    if (!runtimeReady(runtime)) throw new Error(INSTALL_MESSAGE);
    const args = ['-X', 'utf8', file];
    const execution = new vscode.ProcessExecution(runtime.python, args, { cwd: path.dirname(file), env: TASK_ENV });
    const task = new vscode.Task(
      { type: 'process', command: runtime.python, args },
      vscode.TaskScope.Global, 'Chạy ' + path.basename(file), 'Bài tập Python', execution, []
    );
    task.presentationOptions = { reveal: vscode.TaskRevealKind.Always, focus: true };
    await vscode.tasks.executeTask(task);
  } catch (error) {
    await vscode.window.showErrorMessage(error.message);
  }
}

async function offerApply(preview) {
  const { snapshot, response, runtime, code } = preview;
  try {
    const action = await vscode.window.showInformationMessage(resultMessage(response), APPLY);
    if (action !== APPLY) return;
    if (pendingPreview !== preview || !runtimeReady(runtime) || !snapshotUnchanged(snapshot)) {
      await vscode.window.showWarningMessage('Bản xem trước đã hết hiệu lực. Chạy lại lệnh trước khi áp dụng.');
      return;
    }
    const edit = new vscode.WorkspaceEdit();
    edit.replace(snapshot.document.uri, snapshot.range, code);
    const applied = await vscode.workspace.applyEdit(edit);
    if (applied) {
      const dependencies = knownDependencies(code);
      if (!dependencies.length) {
        await vscode.window.showInformationMessage('Đã áp dụng thay đổi. Dùng Hoàn tác để khôi phục nội dung trước đó.');
        return;
      }
      const missing = dependencies.filter((name) => !runtimePackages(runtime).includes(name));
      const help = missing.length
        ? 'Bản cài hiện tại thiếu ' + missing.join(', ') + '. Có thể cài lại bằng setup.py --profile full.'
        : 'Lưu file rồi dùng lệnh "' + RUN_SAVED_FILE + '" khi Python của IDE thiếu thư viện.';
      const action = await vscode.window.showInformationMessage(
        'Đã áp dụng thay đổi. Mã dùng ' + dependencies.join(', ') + '. ' + help, PYTHON_RUNTIME_INFO
      );
      if (action === PYTHON_RUNTIME_INFO) await showPythonRuntime();
    } else {
      await vscode.window.showWarningMessage('IDE không áp dụng được thay đổi. Mở lại file rồi thử lại.');
    }
  } catch (error) {
    await vscode.window.showErrorMessage(error.message);
  } finally {
    if (pendingPreview === preview) pendingPreview = undefined;
  }
}

async function showPreview(snapshot, response, runtime, signal) {
  const { document, source, replaceStart, replaceEnd } = snapshot;
  // Normalize exactly as the editor will when inserting into this document.
  const newline = document.eol === vscode.EndOfLine.CRLF ? '\r\n' : '\n';
  const code = response.code.replace(/\r\n|\r|\n/g, newline);
  const candidate = source.slice(0, replaceStart) + code + source.slice(replaceEnd);
  if (candidate === source) {
    await vscode.window.showInformationMessage('Kết quả giống nội dung hiện tại. ' + resultMessage(response));
    return;
  }

  const id = randomUUID();
  const original = vscode.Uri.from({ scheme: PREVIEW_SCHEME, path: '/' + id + '/Ban-goc.py' });
  const proposed = vscode.Uri.from({ scheme: PREVIEW_SCHEME, path: '/' + id + '/De-xuat.py' });
  previewDocuments.set(original.toString(), source);
  previewDocuments.set(proposed.toString(), candidate);
  try {
    await vscode.commands.executeCommand(
      'vscode.diff', original, proposed, statusLabel(response) + ' — ' + path.basename(document.fileName)
    );
  } catch (error) {
    previewDocuments.delete(original.toString());
    previewDocuments.delete(proposed.toString());
    throw error;
  }

  if (signal.aborted) return;
  const preview = { snapshot, response, runtime, code };
  pendingPreview = preview;
  // Keep the diff open, but release the active operation while the user reviews it.
  void offerApply(preview);
}

async function requestSuggestion(mode, provider = 'offline') {
  if (disabled || uninstalling) return;
  if (activeOperation) {
    await vscode.window.showInformationMessage('Hãy hoàn tất hoặc hủy yêu cầu đang mở.');
    return;
  }

  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== 'python' ||
      !['file', 'untitled'].includes(editor.document.uri.scheme)) {
    await vscode.window.showWarningMessage('Mở file Python cần xử lý.');
    return;
  }
  if (editor.selections.length !== 1) {
    await vscode.window.showWarningMessage('Chọn một vùng mã hoặc đặt một con trỏ để xử lý cả file.');
    return;
  }
  const snapshot = takeSnapshot(editor);
  const text = snapshot.source.slice(snapshot.replaceStart, snapshot.replaceEnd);
  if (!text.trim()) {
    await vscode.window.showWarningMessage('Nhập đề bài hoặc mã Python vào file trước khi chạy.');
    return;
  }
  // API keys belong in the password input, including when the user pastes an old @cfg example.
  if (/^\s*#\s*@cfg\b/im.test(text)) {
    await vscode.window.showWarningMessage('Xóa dòng @cfg trước khi chạy. Dùng lệnh Cloud để nhập API key theo phiên.');
    return;
  }

  const operation = new AbortController();
  activeOperation = operation;
  pendingPreview = undefined;
  const signal = operation.signal;
  let runtime;
  try {
    runtime = getRuntime();
    if (!runtimeReady(runtime)) throw new Error(INSTALL_MESSAGE);

    const useCloud = provider === 'cloud';
    const useLocal = provider === 'local';
    let credentials;
    if (useCloud) {
      const session = await chooseCredentials();
      if (!session || signal.aborted) return;
      const scope = editor.selection.isEmpty ? 'toàn bộ nội dung file đang mở' : 'nội dung vùng chọn';
      const decision = await vscode.window.showWarningMessage(
        'Gửi ' + scope + ' đến ' + session.provider.label + ' để tạo đề xuất?',
        { modal: true }, 'Gửi'
      );
      if (decision !== 'Gửi' || signal.aborted) return;
      sessionCredentials.set(session.provider.id, session.key);
      credentials = { [session.provider.id]: session.key };
    }
    if (!snapshotUnchanged(snapshot)) {
      await vscode.window.showWarningMessage('File hoặc vùng chọn đã thay đổi. Chạy lại lệnh để lấy nội dung mới.');
      return;
    }
    if (!runtimeReady(runtime)) throw new Error(INSTALL_MESSAGE);

    const payload = JSON.stringify({
      text,
      mode,
      verify: true,
      allow_cloud: useCloud,
      allow_local: useLocal,
      credentials
    });
    await vscode.commands.executeCommand('setContext', RUNNING_CONTEXT, true);
    const watch = setInterval(() => {
      if (!runtimeReady(runtime)) operation.abort();
    }, 500);
    let reply;
    try {
      reply = await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: useCloud ? 'Đang xử lý yêu cầu Cloud' : useLocal ? 'Đang xử lý với AI cục bộ' : 'Đang xử lý offline',
        cancellable: true
      }, async (_progress, token) => {
        const cancelListener = token.onCancellationRequested(() => operation.abort());
        if (token.isCancellationRequested) operation.abort();
        try {
          return await runProcess(
            runtime.python, [path.join(runtime.engineRoot, 'core_engine', 'cli_entry.py')],
            runtime.engineRoot, payload, signal
          );
        } finally {
          cancelListener.dispose();
        }
      });
    } finally {
      clearInterval(watch);
      await vscode.commands.executeCommand('setContext', RUNNING_CONTEXT, false);
    }
    if (signal.aborted || !runtimeReady(runtime)) return;
    if (reply.code !== 0) throw new Error('Bộ xử lý Python gặp lỗi. Chạy lại setup nếu lỗi lặp lại.');

    let response;
    try {
      response = JSON.parse(reply.stdout);
    } catch {
      throw new Error('Bộ xử lý Python trả dữ liệu không hợp lệ.');
    }
    if (!response || typeof response.code !== 'string') {
      throw new Error('Bộ xử lý Python trả dữ liệu không hợp lệ.');
    }
    if (!snapshotUnchanged(snapshot)) {
      await vscode.window.showWarningMessage('File hoặc vùng chọn đã thay đổi trong lúc xử lý. Chạy lại lệnh để xem kết quả mới.');
      return;
    }
    if (response.code.trim()) {
      await showPreview(snapshot, response, runtime, signal);
    } else {
      await vscode.window.showWarningMessage(resultMessage(response));
    }
  } catch (error) {
    if (!signal.aborted) await vscode.window.showErrorMessage(error.message);
  } finally {
    activeOperation = undefined;
  }
}

async function uninstall() {
  if (uninstalling || disabled) return;
  uninstalling = true;
  try {
    const decision = await vscode.window.showWarningMessage(
      'Gỡ Trợ lý bài tập Python khỏi tài khoản Windows này?',
      { modal: true }, 'Gỡ cài đặt'
    );
    if (decision !== 'Gỡ cài đặt') return;

    let runtime;
    try {
      runtime = getRuntime();
    } catch {
      throw new Error('Chạy go_cai_dat.bat để gỡ phiên bản chưa có cấu hình cài đặt.');
    }
    const script = path.join(runtime.engineRoot, 'go_cai_dat.py');
    if (typeof runtime.uninstallPython !== 'string' || !path.isAbsolute(runtime.uninstallPython) ||
        !fs.existsSync(runtime.uninstallPython) || !fs.existsSync(script)) {
      throw new Error('Mở go_cai_dat.bat để chạy trình gỡ từ thư mục tải về.');
    }

    activeOperation?.abort();
    pendingPreview = undefined;
    sessionCredentials.clear();
    const result = await vscode.window.withProgress({
      location: vscode.ProgressLocation.Notification,
      title: 'Đang gỡ Trợ lý bài tập Python'
    }, () => runProcess(runtime.uninstallPython, [script], os.tmpdir()));
    if (result.code !== 0) {
      throw new Error('Gỡ chưa hoàn tất. Chạy go_cai_dat.bat để xem lỗi chi tiết.');
    }

    disabled = true;
    const message = runtime.manualExtension
      ? 'Đã gỡ bộ xử lý. Mở Extensions để gỡ bản VSIX đã cài thủ công, rồi tải lại các cửa sổ IDE.'
      : 'Đã gỡ Trợ lý bài tập Python. Tải lại các cửa sổ IDE đang mở.';
    const action = await vscode.window.showInformationMessage(
      message, 'Tải lại cửa sổ'
    );
    if (action === 'Tải lại cửa sổ') {
      await vscode.commands.executeCommand('workbench.action.reloadWindow');
    }
  } catch (error) {
    await vscode.window.showErrorMessage(error.message);
  } finally {
    uninstalling = false;
  }
}

function activate(context) {
  disabled = false;
  context.subscriptions.push(
    vscode.workspace.registerTextDocumentContentProvider(PREVIEW_SCHEME, {
      provideTextDocumentContent: (uri) => previewDocuments.get(uri.toString()) ?? ''
    }),
    vscode.workspace.onDidCloseTextDocument((document) => {
      if (document.uri.scheme === PREVIEW_SCHEME) previewDocuments.delete(document.uri.toString());
    }),
    vscode.commands.registerCommand(PREFIX + 'instantFormat', () => requestSuggestion('instant')),
    vscode.commands.registerCommand(PREFIX + 'deepFormat', () => requestSuggestion('full')),
    vscode.commands.registerCommand(PREFIX + 'ghostMode', () => requestSuggestion('full', 'cloud')),
    vscode.commands.registerCommand(PREFIX + 'silentFix', () => requestSuggestion('self_fix')),
    vscode.commands.registerCommand(PREFIX + 'localAi', () => requestSuggestion('full', 'local')),
    vscode.commands.registerCommand(PREFIX + 'runSavedFile', runSavedFile),
    vscode.commands.registerCommand(PREFIX + 'showPythonRuntime', showPythonRuntime),
    vscode.commands.registerCommand(PREFIX + 'uninstallAll', uninstall),
    vscode.commands.registerCommand(PREFIX + 'cancelGhost', () => activeOperation?.abort()),
    vscode.commands.registerCommand(PREFIX + 'forgetSessionKeys', () => {
      sessionCredentials.clear();
      return vscode.window.showInformationMessage('Đã xóa API key khỏi phiên IDE hiện tại.');
    })
  );
}

function deactivate() {
  disabled = true;
  activeOperation?.abort();
  pendingPreview = undefined;
  sessionCredentials.clear();
  previewDocuments.clear();
}

module.exports = { activate, deactivate };
