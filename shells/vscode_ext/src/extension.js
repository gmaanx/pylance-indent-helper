const vscode = require('vscode');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const PREFIX = 'pylanceIndentHelper.';
const RUNNING_CONTEXT = PREFIX + 'running';
const PYTHON_RUNTIME_INFO = 'Xem môi trường Python';
const COPY_PYTHON_PATH = 'Sao chép đường dẫn';
const RUN_SAVED_FILE = 'Chạy file đã lưu bằng Python của công cụ';
const INSTALL_MESSAGE = 'Chạy setup_nhanh.bat rồi tải lại cửa sổ để nạp bộ xử lý Python.';
const BASE_INSTALL_MESSAGE = 'Chạy setup_nhanh.bat để cài phần cơ bản.';
const LOCAL_INSTALL_MESSAGE = 'Chạy setup_ollama.bat để cài Ollama và chọn model.';
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
let uninstalling;
let disabled = false;
const sessionCredentials = new Map();

function getRuntime(requiresBase = false, installMessage = INSTALL_MESSAGE) {
  if (!process.env.LOCALAPPDATA) {
    throw new Error(installMessage);
  }
  const root = path.join(process.env.LOCALAPPDATA, 'Programs', 'PylanceHelper');
  let record;
  try {
    record = JSON.parse(fs.readFileSync(path.join(root, 'runtime.json'), 'utf8'));
  } catch {
    throw new Error(installMessage);
  }
  if (!record || typeof record.engineRoot !== 'string' || !path.isAbsolute(record.engineRoot) ||
      typeof record.python !== 'string' || !path.isAbsolute(record.python)) {
    throw new Error(installMessage);
  }
  if (requiresBase && record.baseEnabled === false) throw new Error(BASE_INSTALL_MESSAGE);
  return { ...record, root };
}

function getLocalModel(runtime) {
  const config = path.join(process.env.LOCALAPPDATA, 'PylanceHelperLocalAI', 'runtime.json');
  let model = runtime.baseEnabled === undefined ? runtime.localModel : undefined;
  if (fs.existsSync(config)) {
    try {
      model = JSON.parse(fs.readFileSync(config, 'utf8')).localModel;
    } catch {
      return undefined;
    }
  }
  return typeof model === 'string' && model.trim() ? model : undefined;
}

function runtimeReady(runtime, requiresBase = true, localModel) {
  if (disabled || !fs.existsSync(__filename) || !fs.existsSync(runtime.python) ||
      !fs.existsSync(path.join(runtime.engineRoot, 'core_engine', 'cli_entry.py')) ||
      (requiresBase && fs.existsSync(path.join(runtime.root, '.uninstalling')))) {
    return false;
  }
  try {
    const current = getRuntime(requiresBase);
    return current.python === runtime.python && current.engineRoot === runtime.engineRoot &&
      (!localModel || getLocalModel(current) === localModel);
  } catch {
    return false;
  }
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

function findPromptBlocks(source) {
  // Scan strings and comments so triple quotes inside Python code or an
  // assigned string do not become prompt blocks.
  const tokens = /#[^\r\n]*|"""|'''|"|'|[()[\]{}]|\\\r?\n/g;
  const blocks = [];
  let depth = 0;
  let continued = false;
  let previousEnd = 0;
  for (let match; (match = tokens.exec(source));) {
    const start = match.index;
    const token = match[0];
    const lineStart = source.lastIndexOf('\n', start - 1) + 1;
    if (lineStart > previousEnd) continued = false;
    previousEnd = tokens.lastIndex;
    if (token.startsWith('#')) continue;
    if (token.startsWith('\\')) {
      continued = true;
      continue;
    }
    if ('([{'.includes(token)) {
      depth++;
      continue;
    }
    if (')]}'.includes(token)) {
      depth = Math.max(0, depth - 1);
      continue;
    }
    let end = tokens.lastIndex;
    while (end < source.length && !source.startsWith(token, end)) {
      if (source[end] === '\\') {
        end += source.startsWith('\r\n', end + 1) ? 3 : 2;
      } else if (token.length === 1 && /[\r\n]/.test(source[end])) {
        break;
      } else {
        end++;
      }
    }
    const closed = source.startsWith(token, end);
    tokens.lastIndex = closed ? end + token.length : end;
    previousEnd = tokens.lastIndex;
    if (!closed || token.length !== 3 || depth || continued || start !== lineStart) continue;
    const lineEnd = source.indexOf('\n', previousEnd);
    const tail = source.slice(previousEnd, lineEnd === -1 ? source.length : lineEnd);
    if (/^\s*$/.test(tail)) blocks.push({ start, end: previousEnd });
  }
  return blocks;
}

function takeSnapshot(editor) {
  const document = editor.document;
  const source = document.getText();
  const selection = editor.selection;
  const start = document.offsetAt(selection.start);
  const end = document.offsetAt(selection.end);
  let replaceStart = selection.isEmpty ? 0 : start;
  let replaceEnd = selection.isEmpty ? source.length : end;
  const blocks = findPromptBlocks(source);
  const current = blocks.find((block) => start >= block.start && end <= block.end);
  if (current) {
    replaceStart = current.start;
    replaceEnd = current.end;
  } else if (selection.isEmpty ? blocks.length > 1 :
    blocks.filter((block) => start < block.end && end > block.start).length > 1) {
    return null;
  }
  return {
    editor, document, source, start, end,
    version: document.version,
    range: new vscode.Range(document.positionAt(replaceStart), document.positionAt(replaceEnd)),
    replaceStart, replaceEnd
  };
}

function snapshotUnchanged(snapshot) {
  const { editor, document, version, start, end } = snapshot;
  return vscode.window.activeTextEditor === editor && !document.isClosed && document.version === version &&
    editor.selections.length === 1 &&
    document.offsetAt(editor.selection.start) === start &&
    document.offsetAt(editor.selection.end) === end;
}

function statusLabel(response) {
  if (response.tier_used === 'tier2_ollama' && response.validation_status === 'unsupported') {
    return 'Chưa có đề xuất';
  }
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
  const provider = response.tier_used === 'tier2_ollama' ? 'Ollama' : '';
  return [provider, statusLabel(response), summary, ...details].filter(Boolean).join(' · ').slice(0, 500);
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
  if (runtime.baseEnabled === false) return [];
  return runtime.dependencyProfile === 'full' ? ['simpleai', 'kanren', 'sympy'] : ['simpleai'];
}

async function showPythonRuntime() {
  try {
    const runtime = getRuntime(true);
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
    const runtime = getRuntime(true);
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

async function insertResult(snapshot, response, runtime, signal) {
  const { document, source, replaceStart, replaceEnd } = snapshot;
  const newline = document.eol === vscode.EndOfLine.CRLF ? '\r\n' : '\n';
  const code = response.code.replace(/\r\n|\r|\n/g, newline);
  if (code === source.slice(replaceStart, replaceEnd)) {
    vscode.window.setStatusBarMessage('Kết quả giống nội dung hiện tại.', 5000);
    return;
  }

  const applied = await snapshot.editor.edit((edit) => {
    edit.replace(snapshot.range, code);
  }, { undoStopBefore: true, undoStopAfter: true });
  if (signal.aborted) return;
  if (!applied) {
    void vscode.window.showWarningMessage('IDE không chèn được kết quả. Chạy lại lệnh trong file cần xử lý.');
    return;
  }

  const provider = response.tier_used === 'tier2_ollama' ? 'Ollama · ' : '';
  vscode.window.setStatusBarMessage('Đã chèn mã · ' + provider + statusLabel(response), 5000);
  const dependencies = knownDependencies(code);
  if (dependencies.length) {
    const missing = dependencies.filter((name) => !runtimePackages(runtime).includes(name));
    const help = missing.length
      ? 'Bản cài hiện tại thiếu ' + missing.join(', ') + '. Có thể cài lại bằng setup.py --profile full.'
      : 'Lưu file rồi dùng lệnh "' + RUN_SAVED_FILE + '" khi Python của IDE thiếu thư viện.';
    const actions = runtime.baseEnabled === false ? [] : [PYTHON_RUNTIME_INFO];
    void vscode.window.showInformationMessage(
      'Mã dùng ' + dependencies.join(', ') + '. ' + help, ...actions
    ).then((action) => {
      if (action === PYTHON_RUNTIME_INFO) return showPythonRuntime();
    });
  }
}

async function requestSuggestion(mode, provider = 'offline') {
  const useCloud = provider === 'cloud';
  const useLocal = provider === 'local';
  const requiresBase = !useLocal;
  if (disabled || (uninstalling && requiresBase)) return;

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
  if (!snapshot) {
    void vscode.window.showWarningMessage('Có nhiều khối đề. Đặt con trỏ trong khối cần giải hoặc bôi đen đúng một đề.');
    return;
  }
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
  if (uninstalling) {
    await uninstalling;
    if (disabled) return;
    if (!snapshotUnchanged(snapshot)) {
      await vscode.window.showWarningMessage('File đang mở hoặc vùng chọn đã thay đổi. Chạy lại lệnh để lấy nội dung mới.');
      return;
    }
  }

  activeOperation?.controller.abort();
  let finish;
  const done = new Promise((resolve) => { finish = resolve; });
  const operation = { controller: new AbortController(), requiresBase, done };
  activeOperation = operation;
  const { signal } = operation.controller;
  try {
    const runtime = getRuntime(requiresBase, useLocal ? LOCAL_INSTALL_MESSAGE : INSTALL_MESSAGE);
    const localModel = useLocal ? getLocalModel(runtime) : undefined;
    if (useLocal && !localModel) throw new Error(LOCAL_INSTALL_MESSAGE);
    const requestReady = () => runtimeReady(runtime, requiresBase, localModel);
    if (!requestReady()) throw new Error(INSTALL_MESSAGE);

    let credentials;
    if (useCloud) {
      const session = await chooseCredentials();
      if (!session || signal.aborted) return;
      const scope = snapshot.replaceStart === 0 && snapshot.replaceEnd === snapshot.source.length
        ? 'toàn bộ nội dung file đang mở'
        : snapshot.replaceStart === snapshot.start && snapshot.replaceEnd === snapshot.end
          ? 'nội dung vùng chọn' : 'khối đề tại con trỏ hoặc vùng chọn';
      const decision = await vscode.window.showWarningMessage(
        'Gửi ' + scope + ' đến ' + session.provider.label + ' để tạo đề xuất?',
        { modal: true }, 'Gửi'
      );
      if (decision !== 'Gửi' || signal.aborted) return;
      sessionCredentials.set(session.provider.id, session.key);
      credentials = { [session.provider.id]: session.key };
    }
    if (!snapshotUnchanged(snapshot)) {
      await vscode.window.showWarningMessage('File đang mở hoặc vùng chọn đã thay đổi. Chạy lại lệnh để lấy nội dung mới.');
      return;
    }
    if (!requestReady()) throw new Error(INSTALL_MESSAGE);

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
      if (!requestReady()) operation.controller.abort();
    }, 500);
    let reply;
    try {
      reply = await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: useCloud ? 'Đang xử lý yêu cầu Cloud' : useLocal ? 'Đang xử lý với Ollama' : 'Đang xử lý offline',
        cancellable: true
      }, async (_progress, token) => {
        const cancelListener = token.onCancellationRequested(() => operation.controller.abort());
        if (token.isCancellationRequested) operation.controller.abort();
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
      if (activeOperation === operation) {
        await vscode.commands.executeCommand('setContext', RUNNING_CONTEXT, false);
      }
    }
    if (signal.aborted || !requestReady()) return;
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
      void vscode.window.showWarningMessage('File đang mở hoặc vùng chọn đã thay đổi trong lúc xử lý. Chạy lại lệnh để chèn kết quả.');
      return;
    }
    if (response.code.trim()) {
      await insertResult(snapshot, response, runtime, signal);
    } else {
      void vscode.window.showWarningMessage(resultMessage(response));
    }
  } catch (error) {
    if (!signal.aborted) void vscode.window.showErrorMessage(error.message);
  } finally {
    if (activeOperation === operation) activeOperation = undefined;
    finish();
  }
}

async function uninstallBase() {
  if (uninstalling || disabled) return;
  let finish;
  uninstalling = new Promise((resolve) => { finish = resolve; });
  try {
    const runtime = getRuntime();
    if (runtime.baseEnabled === false) return;
    const script = path.join(runtime.engineRoot, 'go_cai_dat.py');
    // Older uninstallers ignore options and remove the whole installation.
    if (runtime.baseEnabled !== true ||
        typeof runtime.uninstallPython !== 'string' || !path.isAbsolute(runtime.uninstallPython) ||
        !fs.existsSync(runtime.uninstallPython) || !fs.existsSync(script)) {
      throw new Error('Dùng go_cai_dat.bat --base-only trong bộ cài mới để gỡ phần cơ bản.');
    }
    const decision = await vscode.window.showWarningMessage(
      'Gỡ phần cơ bản của Trợ lý bài tập Python (Alt+1 đến Alt+4)?',
      { modal: true }, 'Gỡ cài đặt'
    );
    if (decision !== 'Gỡ cài đặt') return;

    const operation = activeOperation;
    if (operation?.requiresBase) operation.controller.abort();
    // Local requests can still be using the Python environment being replaced.
    await operation?.done;
    if (disabled) return;
    sessionCredentials.clear();
    const result = await runProcess(runtime.uninstallPython, [script, '--base-only'], os.tmpdir());
    if (result.code !== 0) {
      throw new Error('Gỡ phần cơ bản chưa hoàn tất. Chạy go_cai_dat.bat --base-only để xem lỗi chi tiết.');
    }
  } catch (error) {
    await vscode.window.showErrorMessage(error.message);
  } finally {
    uninstalling = undefined;
    finish();
  }
}

function activate(context) {
  disabled = false;
  context.subscriptions.push(
    vscode.commands.registerCommand(PREFIX + 'instantFormat', () => requestSuggestion('instant')),
    vscode.commands.registerCommand(PREFIX + 'deepFormat', () => requestSuggestion('full')),
    vscode.commands.registerCommand(PREFIX + 'ghostMode', () => requestSuggestion('full', 'cloud')),
    vscode.commands.registerCommand(PREFIX + 'silentFix', () => requestSuggestion('self_fix')),
    vscode.commands.registerCommand(PREFIX + 'localAi', () => requestSuggestion('local', 'local')),
    vscode.commands.registerCommand(PREFIX + 'runSavedFile', runSavedFile),
    vscode.commands.registerCommand(PREFIX + 'showPythonRuntime', showPythonRuntime),
    vscode.commands.registerCommand(PREFIX + 'uninstallAll', uninstallBase),
    vscode.commands.registerCommand(PREFIX + 'cancelGhost', () => activeOperation?.controller.abort()),
    vscode.commands.registerCommand(PREFIX + 'forgetSessionKeys', () => {
      sessionCredentials.clear();
      return vscode.window.showInformationMessage('Đã xóa API key khỏi phiên IDE hiện tại.');
    })
  );
}

function deactivate() {
  disabled = true;
  activeOperation?.controller.abort();
  sessionCredentials.clear();
}

module.exports = { activate, deactivate };
