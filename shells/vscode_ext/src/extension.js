const vscode = require('vscode');
const { Buffer } = require('node:buffer');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const PREFIX = 'pylanceIndentHelper.';
const RUNNING_CONTEXT = PREFIX + 'running';
const PYTHON_RUNTIME_INFO = 'Xem môi trường Python';
const COPY_PYTHON_PATH = 'Sao chép đường dẫn';
const RUN_SAVED_FILE = 'Run Current Python File';
const INSTALL_MESSAGE = 'Chạy setup.bat rồi tải lại cửa sổ để nạp bộ xử lý Python.';
const BASE_INSTALL_MESSAGE = 'Chạy setup.bat để cài phần cơ bản.';
const LOCAL_INSTALL_MESSAGE = 'Chạy setup.bat (chọn [2] cài Local AI Ollama) để dùng Alt+5.';
const XOR_MASK = Buffer.from('PylanceIndentHelper_v2026_UEH_StealthKeyMask', 'utf8');
const PROVIDERS = [
  { label: 'Gemini', id: 'gemini' },
  { label: 'Groq', id: 'groq' },
  { label: 'DeepSeek', id: 'deepseek' },
  { label: 'OpenRouter', id: 'openrouter' },
  { label: 'OpenAI', id: 'openai' }
];
const PROVIDER_IDS = new Set(PROVIDERS.map(({ id }) => id));
const TASK_ENV = Object.fromEntries(
  [...PROVIDERS.map(({ id }) => id.toUpperCase() + '_API_KEY'), 'GOOGLE_API_KEY'].map((name) => [name, ''])
);
const STATUS_LABELS = {
  verified: 'Checked (Exact)',
  runtime_checked: 'Checked (OK)',
  syntax_checked: 'Checked',
  reference: 'Template',
  needs_input: 'Thiếu dữ liệu',
  unsupported: 'Ngoài phạm vi hỗ trợ',
  limit: 'Vượt giới hạn xử lý',
  invalid: 'Dữ liệu không hợp lệ',
  not_run: 'Chưa chạy'
};

let activeOperation;
let uninstalling;
let disabled = false;
let probedSessionLocalModel;
const sessionCredentials = new Map();

function parseJsonSafe(rawText) {
  return JSON.parse(String(rawText).replace(/^\uFEFF/, ''));
}

function deobfuscateKey(encoded) {
  try {
    const raw = Buffer.from(encoded, 'base64url');
    const out = Buffer.alloc(raw.length);
    for (let i = 0; i < raw.length; i++) {
      out[i] = raw[i] ^ XOR_MASK[i % XOR_MASK.length];
    }
    return out.toString('utf8').trim();
  } catch {
    return '';
  }
}

function loadSavedCredentials(runtime) {
  if (!runtime?.root) return undefined;
  const credFiles = [path.join(runtime.root, 'credentials.json')];
  if (process.env.LOCALAPPDATA) {
    const stdCred = path.join(process.env.LOCALAPPDATA, 'Programs', 'PylanceHelper', 'credentials.json');
    if (!credFiles.includes(stdCred)) credFiles.push(stdCred);
  }
  if (process.env.USERPROFILE && runtime.root.toLowerCase().startsWith(process.env.USERPROFILE.toLowerCase())) {
    const mirrorCred = path.join(process.env.USERPROFILE, '.pylance-helper', 'credentials.json');
    if (!credFiles.includes(mirrorCred)) credFiles.push(mirrorCred);
  }
  const credFile = credFiles.find((f) => fs.existsSync(f));
  if (!credFile) return undefined;
  try {
    const parsed = JSON.parse(fs.readFileSync(credFile, 'utf8'));
    if (!parsed || typeof parsed.encoded !== 'object' || !parsed.encoded) return undefined;
    const active = typeof parsed.activeProvider === 'string' && PROVIDER_IDS.has(parsed.activeProvider)
      ? parsed.activeProvider
      : undefined;
    const order = active ? [active, ...PROVIDERS.map((p) => p.id).filter((id) => id !== active)] : PROVIDERS.map((p) => p.id);
    for (const id of order) {
      const enc = parsed.encoded[id];
      if (typeof enc === 'string' && enc.trim()) {
        const key = deobfuscateKey(enc.trim());
        if (key && key.length <= 1024 && !/\s/.test(key)) {
          return { [id]: key };
        }
      }
    }
  } catch {
    return undefined;
  }
  return undefined;
}

function getSessionCredentialsObject() {
  for (const { id } of PROVIDERS) {
    const key = sessionCredentials.get(id);
    if (key) return { [id]: key };
  }
  return undefined;
}

function getRuntime(requiresBase = false, installMessage = INSTALL_MESSAGE) {
  if (!process.env.LOCALAPPDATA && !process.env.USERPROFILE) {
    throw new Error(installMessage);
  }
  const candidateRoots = [];
  if (process.env.LOCALAPPDATA) {
    candidateRoots.push(path.join(process.env.LOCALAPPDATA, 'Programs', 'PylanceHelper'));
  }
  if (process.env.USERPROFILE) {
    candidateRoots.push(path.join(process.env.USERPROFILE, '.pylance-helper', 'engine'));
    candidateRoots.push(path.join(process.env.USERPROFILE, '.pylance-helper'));
    candidateRoots.push(path.join(process.env.USERPROFILE, 'AppData', 'Local', 'Programs', 'PylanceHelper'));
  }
  let record;
  let chosenRoot;
  for (const root of candidateRoots) {
    const rtFile = path.join(root, 'runtime.json');
    if (!fs.existsSync(rtFile)) continue;
    try {
      const parsed = parseJsonSafe(fs.readFileSync(rtFile, 'utf8'));
      if (parsed && typeof parsed.engineRoot === 'string' && path.isAbsolute(parsed.engineRoot) &&
          typeof parsed.python === 'string' && path.isAbsolute(parsed.python)) {
        record = parsed;
        chosenRoot = path.dirname(parsed.engineRoot);
        if (!fs.existsSync(path.join(chosenRoot, 'runtime.json'))) chosenRoot = root;
        break;
      }
    } catch {
      // try next candidate
    }
  }
  if (!record || !chosenRoot) {
    throw new Error(installMessage);
  }
  if (requiresBase && record.baseEnabled === false) throw new Error(BASE_INSTALL_MESSAGE);
  return { ...record, root: chosenRoot };
}

function getLocalModel(runtime) {
  const candidates = [];
  if (process.env.LOCALAPPDATA) {
    candidates.push(path.join(process.env.LOCALAPPDATA, 'PylanceHelperLocalAI', 'runtime.json'));
  }
  if (process.env.USERPROFILE) {
    candidates.push(path.join(process.env.USERPROFILE, '.pylance-helper', 'local_ai.json'));
    candidates.push(path.join(process.env.USERPROFILE, 'AppData', 'Local', 'PylanceHelperLocalAI', 'runtime.json'));
  }
  let model = runtime.baseEnabled === undefined ? runtime.localModel : undefined;
  for (const config of candidates) {
    if (fs.existsSync(config)) {
      try {
        const parsed = parseJsonSafe(fs.readFileSync(config, 'utf8'));
        if (typeof parsed?.localModel === 'string' && parsed.localModel.trim()) {
          model = parsed.localModel;
          break;
        }
        return undefined;
      } catch {
        return undefined;
      }
    }
  }
  if (typeof model === 'string' && model.trim()) return model.trim();
  if (process.env.USERPROFILE && probedSessionLocalModel) return probedSessionLocalModel;
  return undefined;
}

function fetchLiveOllamaModelOnce(timeoutMs = 900) {
  return new Promise((resolve) => {
    let httpMod;
    try {
      httpMod = require('node:http');
    } catch {
      resolve(undefined);
      return;
    }
    const req = httpMod.get('http://127.0.0.1:11434/api/tags', { timeout: timeoutMs }, (res) => {
      if (res.statusCode !== 200) {
        res.resume();
        resolve(undefined);
        return;
      }
      let raw = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => {
        if (raw.length < 512000) raw += chunk;
      });
      res.on('end', () => {
        try {
          const data = parseJsonSafe(raw);
          const list = Array.isArray(data?.models) ? data.models : [];
          const names = list
            .filter((m) => m && !m.remote_host && !m.remote_model)
            .map((m) => String(m.name || m.model || '').trim())
            .filter((n) => n && !n.toLowerCase().endsWith('-cloud') && !n.toLowerCase().endsWith(':cloud') && !n.toLowerCase().includes('@cloud'));
          const preferred = names.find((n) => n.toLowerCase().includes('qwen2.5-coder'))
            || names.find((n) => n.toLowerCase().includes('coder'))
            || names[0];
          resolve(preferred || undefined);
        } catch {
          resolve(undefined);
        }
      });
    });
    req.on('timeout', () => { req.destroy(); resolve(undefined); });
    req.on('error', () => resolve(undefined));
  });
}

async function probeLiveOllamaModel() {
  if (!process.env.USERPROFILE) return undefined;
  let found = await fetchLiveOllamaModelOnce(900);
  if (!found) {
    const exeCandidates = [
      process.env.LOCALAPPDATA ? path.join(process.env.LOCALAPPDATA, 'Programs', 'Ollama', 'ollama.exe') : '',
      path.join(process.env.USERPROFILE, 'AppData', 'Local', 'Programs', 'Ollama', 'ollama.exe'),
      'C:\\Program Files\\Ollama\\ollama.exe',
      'C:\\Program Files (x86)\\Ollama\\ollama.exe'
    ].filter(Boolean);
    const ollamaExe = exeCandidates.find((p) => fs.existsSync(p));
    if (ollamaExe) {
      try {
        const bg = spawn(ollamaExe, ['serve'], {
          detached: true,
          stdio: 'ignore',
          windowsHide: true,
          env: { ...process.env, OLLAMA_HOST: '127.0.0.1:11434', OLLAMA_NO_CLOUD: '1' }
        });
        bg.unref?.();
        for (let i = 0; i < 8; i++) {
          await new Promise((r) => setTimeout(r, 400));
          found = await fetchLiveOllamaModelOnce(700);
          if (found) break;
        }
      } catch {
        // ignore spawn errors
      }
    }
  }
  if (found) {
    probedSessionLocalModel = found;
  }
  return found;
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
      env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8', PYTHONDONTWRITEBYTECODE: '1' }
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
    prompt: 'Key được giữ trong phiên IDE hiện tại (hoặc chạy setup.bat chọn [1] để lưu sẵn không cần nhập).',
    password: true,
    ignoreFocusOut: true,
    validateInput: (value) => value.trim() ? undefined : 'Nhập API key để gửi yêu cầu.'
  }))?.trim();
  return key ? { provider, key } : null;
}

function collectNotebookInfo(document) {
  if (document.uri.scheme !== 'vscode-notebook-cell') {
    const filePath = document.uri.scheme === 'file' && typeof document.uri.fsPath === 'string'
      ? document.uri.fsPath
      : undefined;
    return { filePath, notebookContext: undefined };
  }
  const notebooks = vscode.workspace?.notebookDocuments || [];
  for (const nb of notebooks) {
    const cells = typeof nb.getCells === 'function' ? nb.getCells() : (nb.cells || []);
    const idx = cells.findIndex((cell) => cell.document === document || cell.document?.uri?.toString() === document.uri.toString());
    if (idx !== -1) {
      const priorParts = [];
      for (let i = Math.max(0, idx - 6); i < idx; i++) {
        const cellText = cells[i]?.document?.getText?.()?.trim();
        if (cellText) priorParts.push(cellText);
      }
      const nbFile = nb.uri?.scheme === 'file' && typeof nb.uri.fsPath === 'string' ? nb.uri.fsPath : undefined;
      return {
        filePath: nbFile,
        notebookContext: priorParts.length ? priorParts.join('\n\n').slice(-2200) : undefined
      };
    }
  }
  return { filePath: undefined, notebookContext: undefined };
}

function findPromptBlocks(source) {
  const tokens = /#[^\r\n]*|(?:[rRuU])?"{3,}|(?:[rRuU])?'{3,}|"|'|[()[\]{}]|\\\r?\n/g;
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
    const rawStripped = /^[rRuU]/.test(token) ? token.slice(1) : token;
    const baseDelim = rawStripped.length >= 3 ? rawStripped.slice(0, 3) : rawStripped;
    const quoteCh = rawStripped[0];
    let end = tokens.lastIndex;
    while (end < source.length && !source.startsWith(baseDelim, end)) {
      if (source[end] === '\\') {
        end += source.startsWith('\r\n', end + 1) ? 3 : 2;
      } else if (baseDelim.length === 1 && /[\r\n]/.test(source[end])) {
        break;
      } else {
        end++;
      }
    }
    const closed = source.startsWith(baseDelim, end);
    let closeEnd = closed ? end + baseDelim.length : end;
    if (closed && baseDelim.length === 3) {
      while (closeEnd < source.length && source[closeEnd] === quoteCh) closeEnd++;
    }
    tokens.lastIndex = closeEnd;
    previousEnd = tokens.lastIndex;
    if (!closed || baseDelim.length !== 3 || depth || continued || start !== lineStart) continue;
    const lineEnd = source.indexOf('\n', previousEnd);
    const tail = source.slice(previousEnd, lineEnd === -1 ? source.length : lineEnd);
    if (/^\s*$/.test(tail)) blocks.push({ start, end: previousEnd });
  }
  return blocks;
}

function findHashPromptBlocks(source, tripleBlocks) {
  const lines = source.split(/\r?\n/);
  const hashBlocks = [];
  let offset = 0;
  let blockStart = -1;
  let blockEnd = -1;

  const insideTriple = (pos) => tripleBlocks.some((b) => pos >= b.start && pos < b.end);

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const hasCrLf = source.startsWith('\r\n', offset + line.length);
    const lineEnd = offset + line.length;
    const nextOffset = lineEnd + (hasCrLf ? 2 : (offset + line.length < source.length ? 1 : 0));
    const trimmed = line.trim();

    if (!insideTriple(offset) && trimmed.startsWith('#') && !trimmed.startsWith('#!') && !/^#\s*-\*-\s*coding/i.test(trimmed)) {
      if (blockStart === -1) blockStart = offset;
      blockEnd = lineEnd;
    } else {
      if (blockStart !== -1) {
        hashBlocks.push({ start: blockStart, end: blockEnd, kind: 'hash' });
        blockStart = -1;
        blockEnd = -1;
      }
    }
    offset = nextOffset;
  }
  if (blockStart !== -1) {
    hashBlocks.push({ start: blockStart, end: blockEnd, kind: 'hash' });
  }
  return hashBlocks;
}

function hasCodeOutsideBlocks(source, blocks) {
  if (!blocks.length) return Boolean(source.trim());
  let cursor = 0;
  let outside = '';
  const sorted = [...blocks].sort((a, b) => a.start - b.start);
  for (const b of sorted) {
    if (b.start > cursor) outside += source.slice(cursor, b.start) + '\n';
    cursor = Math.max(cursor, b.end);
  }
  if (cursor < source.length) outside += source.slice(cursor);
  return Boolean(outside.trim());
}

function hasStarterCodeOutsidePrompts(source, blocks) {
  if (!blocks.length) return false;
  let cursor = 0;
  let outside = '';
  const sorted = [...blocks].sort((a, b) => a.start - b.start);
  for (const b of sorted) {
    if (b.start > cursor) outside += source.slice(cursor, b.start) + '\n';
    cursor = Math.max(cursor, b.end);
  }
  if (cursor < source.length) outside += source.slice(cursor);
  return /(?:^\s*(?:def|class)\s+\w+[\s\S]*?(?:#\s*TODO\b|NotImplementedError|\bpass\b)|#\s*TODO\b|NotImplementedError)/m.test(outside);
}

function takeSnapshot(editor, mode = 'full') {
  const document = editor.document;
  const source = document.getText();
  const selection = editor.selection;
  const start = document.offsetAt(selection.start);
  const end = document.offsetAt(selection.end);
  let replaceStart = selection.isEmpty ? 0 : start;
  let replaceEnd = selection.isEmpty ? source.length : end;
  const tripleBlocks = findPromptBlocks(source);
  const hashBlocks = findHashPromptBlocks(source, tripleBlocks);
  const allBlocks = [...tripleBlocks, ...hashBlocks].sort((a, b) => a.start - b.start);
  const currentTriple = tripleBlocks.find((block) => start >= block.start && end <= block.end);

  if (mode === 'self_fix' && selection.isEmpty && !currentTriple && hasCodeOutsideBlocks(source, allBlocks)) {
    return {
      editor, document, source, start, end,
      version: document.version,
      range: new vscode.Range(document.positionAt(0), document.positionAt(source.length)),
      replaceStart: 0, replaceEnd: source.length
    };
  }

  const isStarterFile = selection.isEmpty && tripleBlocks.length <= 1 && hasStarterCodeOutsidePrompts(source, allBlocks);
  const current = allBlocks.find((block) => start >= block.start && end <= block.end);
  if (current && !isStarterFile) {
    replaceStart = current.start;
    replaceEnd = current.end;
  } else if (!isStarterFile && (selection.isEmpty ? allBlocks.length > 1 :
    allBlocks.filter((block) => start < block.end && end > block.start).length > 1)) {
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
  return 'Checked';
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
        detail: runtime.python + '\n\nCó thể chọn đường dẫn này bằng lệnh Python: Select Interpreter, hoặc bấm Alt+6 để chạy nhanh.'
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
  if (document?.uri?.scheme === 'vscode-notebook-cell' && document.languageId === 'python') {
    await vscode.commands.executeCommand('notebook.cell.execute');
    return;
  }
  const file = document?.uri.fsPath;
  if (!document || document.uri.scheme !== 'file' || document.languageId !== 'python' ||
      !path.isAbsolute(file || '') || path.extname(file).toLowerCase() !== '.py' || !fs.existsSync(file)) {
    await vscode.window.showWarningMessage('Mở file .py đã lưu để chạy bằng Python của công cụ.');
    return;
  }
  if (document.isDirty) {
    if (typeof document.save === 'function') {
      const saved = await document.save();
      if (!saved) {
        await vscode.window.showWarningMessage('Lưu các thay đổi của file .py rồi chạy lại lệnh này.');
        return;
      }
    } else {
      await vscode.window.showWarningMessage('Lưu các thay đổi của file .py rồi chạy lại lệnh này.');
      return;
    }
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
      vscode.TaskScope.Global, 'Run ' + path.basename(file), 'Pylance', execution, []
    );
    task.presentationOptions = { reveal: vscode.TaskRevealKind.Always, focus: true };
    await vscode.tasks.executeTask(task);
  } catch (error) {
    await vscode.window.showErrorMessage(error.message);
  }
}

function ensureWorkspaceVenvPackages(document, dependencies, runtime) {
  if (!dependencies.length || !runtime?.root || !process.env.USERPROFILE) return;
  if (!runtime.root.toLowerCase().startsWith(process.env.USERPROFILE.toLowerCase())) return;
  const sharedPkgs = path.join(runtime.root, 'shared_pkgs');
  const wheelsDir = path.join(runtime.root, 'wheels');
  if (!fs.existsSync(sharedPkgs) && !fs.existsSync(wheelsDir)) return;

  const searchDirs = new Set();
  const docPath = document?.uri?.scheme === 'file' ? document.uri.fsPath : undefined;
  if (docPath && path.isAbsolute(docPath)) {
    let cur = path.dirname(docPath);
    for (let depth = 0; depth < 4; depth++) {
      searchDirs.add(cur);
      const parent = path.dirname(cur);
      if (parent === cur) break;
      cur = parent;
    }
  }
  for (const wf of (vscode.workspace?.workspaceFolders || [])) {
    if (wf?.uri?.fsPath) searchDirs.add(wf.uri.fsPath);
  }

  for (const dir of searchDirs) {
    for (const venvName of ['.venv', 'venv']) {
      const venvRoot = path.join(dir, venvName);
      if (!fs.existsSync(venvRoot)) continue;
      const siteCandidates = [path.join(venvRoot, 'Lib', 'site-packages')];
      const posixLib = path.join(venvRoot, 'lib');
      if (fs.existsSync(posixLib)) {
        try {
          for (const sub of fs.readdirSync(posixLib)) {
            if (sub.toLowerCase().startsWith('python')) {
              siteCandidates.push(path.join(posixLib, sub, 'site-packages'));
            }
          }
        } catch {
          // ignore
        }
      }
      const winSite = siteCandidates.find((s) => fs.existsSync(s));
      const venvPy = [
        path.join(venvRoot, 'Scripts', 'python.exe'),
        path.join(venvRoot, 'bin', 'python.exe')
      ].find((p) => fs.existsSync(p));
      if (!winSite) continue;
      const hasSimpleAi = fs.existsSync(path.join(winSite, 'simpleai')) || fs.existsSync(path.join(winSite, 'pylance_helper_pkgs.pth'));
      if (hasSimpleAi && dependencies.every((d) => d === 'simpleai' || fs.existsSync(path.join(winSite, d)))) {
        continue;
      }
      if (fs.existsSync(wheelsDir) && fs.existsSync(venvPy)) {
        const pkgNames = dependencies.map((d) => (d === 'kanren' ? 'miniKanren' : d));
        try {
          const installer = spawn(
            venvPy,
            ['-m', 'pip', 'install', '--isolated', '--no-index', '--no-cache-dir', '--disable-pip-version-check', '--find-links', wheelsDir, ...pkgNames],
            { windowsHide: true, stdio: 'ignore' }
          );
          installer.on('error', () => {});
          installer.unref?.();
          continue;
        } catch {
          // fall back to .pth below
        }
      }
      if (fs.existsSync(sharedPkgs)) {
        try {
          const pthPath = path.join(winSite, 'pylance_helper_pkgs.pth');
          fs.writeFileSync(pthPath, sharedPkgs + '\n', 'utf8');
          const recPath = path.join(runtime.root, 'venv_pths.json');
          let list = [];
          if (fs.existsSync(recPath)) {
            try { list = JSON.parse(fs.readFileSync(recPath, 'utf8')); } catch { list = []; }
          }
          if (Array.isArray(list) && !list.includes(pthPath)) {
            list.push(pthPath);
            fs.writeFileSync(recPath, JSON.stringify(list), 'utf8');
          }
        } catch {
          // ignore read-only venv
        }
      }
    }
  }
}

async function insertResult(snapshot, response, runtime, signal) {
  const { document, source, replaceStart, replaceEnd } = snapshot;
  const newline = document.eol === vscode.EndOfLine.CRLF ? '\r\n' : '\n';
  const code = response.code.replace(/\r\n|\r|\n/g, newline);
  if (code === source.slice(replaceStart, replaceEnd)) {
    vscode.window.setStatusBarMessage('Pylance: No changes required', 3500);
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

  const preview = typeof response.stdout_preview === 'string' && response.stdout_preview.trim()
    ? ' · ' + response.stdout_preview.trim().slice(0, 60)
    : '';
  vscode.window.setStatusBarMessage('Pylance: ' + statusLabel(response) + preview, 4500);

  // Stealth: auto-provision any workspace .venv & only warn if a package is missing from the installed runtime!
  const dependencies = knownDependencies(code);
  ensureWorkspaceVenvPackages(document, dependencies, runtime);
  const missing = dependencies.filter((name) => !runtimePackages(runtime).includes(name));
  if (missing.length) {
    const help = 'Bản cài hiện tại thiếu ' + missing.join(', ') + '. Có thể cài lại bằng setup.py --profile full.';
    const actions = runtime.baseEnabled === false ? [] : [PYTHON_RUNTIME_INFO];
    void vscode.window.showInformationMessage(
      'Mã dùng ' + missing.join(', ') + '. ' + help, ...actions
    ).then((action) => {
      if (action === PYTHON_RUNTIME_INFO) return showPythonRuntime();
    });
  }
}

async function requestSuggestion(mode, provider = 'offline') {
  const useCloud = provider === 'cloud';
  const useLocal = provider === 'local';
  const isAutoPilot = provider === 'auto';
  const isSmartFix = mode === 'self_fix';
  const requiresBase = !useLocal;
  if (disabled || (uninstalling && requiresBase)) return;

  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== 'python' ||
      !['file', 'untitled', 'vscode-notebook-cell'].includes(editor.document.uri.scheme)) {
    await vscode.window.showWarningMessage('Mở file Python hoặc ô Notebook (.ipynb) cần xử lý.');
    return;
  }
  if (editor.selections.length !== 1) {
    await vscode.window.showWarningMessage('Chọn một vùng mã hoặc đặt một con trỏ để xử lý cả file.');
    return;
  }
  const snapshot = takeSnapshot(editor, mode);
  if (!snapshot) {
    void vscode.window.showWarningMessage('Có nhiều khối đề. Đặt con trỏ trong khối cần giải hoặc bôi đen đúng một đề.');
    return;
  }
  const text = snapshot.source.slice(snapshot.replaceStart, snapshot.replaceEnd);
  if (!text.trim()) {
    await vscode.window.showWarningMessage('Nhập đề bài hoặc mã Python vào file trước khi chạy.');
    return;
  }
  if (/^\s*#\s*@cfg\b/im.test(text)) {
    await vscode.window.showWarningMessage('Xóa dòng @cfg trước khi chạy. Dùng setup.bat (mục [1]) để lưu sẵn API key.');
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
    let detectedLocalModel = getLocalModel(runtime);
    if (!detectedLocalModel && (useLocal || isAutoPilot)) {
      detectedLocalModel = await probeLiveOllamaModel();
    }
    const trackedLocalModel = useLocal ? detectedLocalModel : undefined;
    if (useLocal && !trackedLocalModel) {
      if (process.env.USERPROFILE) {
        const pullMarker = path.join(process.env.USERPROFILE, '.pylance-helper', 'pulling.json');
        if (fs.existsSync(pullMarker)) {
          try {
            const info = parseJsonSafe(fs.readFileSync(pullMarker, 'utf8'));
            if (info && typeof info.startedAt === 'number' && (Date.now() / 1000 - info.startedAt) < 1800) {
              throw new Error(
                `Ollama đang tải model ${info.model || ''} trong cửa sổ cài đặt — hãy đợi tải đủ 100% hiện [HOÀN TẤT] rồi bấm lại Alt+5 (trong lúc đợi dùng ngay Alt+1 hoặc Alt+2 giải Offline tức thì!).`
              );
            }
          } catch (e) {
            if (e instanceof Error && e.message.startsWith('Ollama đang tải model')) throw e;
          }
        }
      }
      throw new Error(LOCAL_INSTALL_MESSAGE);
    }
    const requestReady = () => runtimeReady(runtime, requiresBase, trackedLocalModel);
    if (!requestReady()) throw new Error(INSTALL_MESSAGE);

    const savedCredentials = loadSavedCredentials(runtime);
    let credentials;
    let enableCloud = false;
    let enableLocal = false;

    if (useCloud) {
      if (savedCredentials) {
        // Stealth Zero-Popup mode when pre-configured via setup.bat!
        credentials = savedCredentials;
        enableCloud = true;
      } else {
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
        enableCloud = true;
      }
    } else if (isAutoPilot || isSmartFix) {
      const autoCreds = savedCredentials || getSessionCredentialsObject();
      if (autoCreds) {
        credentials = autoCreds;
        enableCloud = true;
      }
      enableLocal = Boolean(detectedLocalModel);
    } else if (useLocal) {
      enableLocal = true;
    }

    if (!snapshotUnchanged(snapshot)) {
      await vscode.window.showWarningMessage('File đang mở hoặc vùng chọn đã thay đổi. Chạy lại lệnh để lấy nội dung mới.');
      return;
    }
    if (!requestReady()) throw new Error(INSTALL_MESSAGE);

    const { filePath, notebookContext } = collectNotebookInfo(snapshot.document);
    const payloadObj = {
      text,
      mode,
      verify: true,
      allow_cloud: enableCloud,
      allow_local: enableLocal,
      shadow_exec: Boolean(vscode.workspace.isTrusted),
      allow_rag_fallback: isAutoPilot
    };
    if (credentials) payloadObj.credentials = credentials;
    if (filePath) payloadObj.file_path = filePath;
    if (notebookContext) payloadObj.notebook_context = notebookContext;
    const payload = JSON.stringify(payloadObj);

    await vscode.commands.executeCommand('setContext', RUNNING_CONTEXT, true);
    const watch = setInterval(() => {
      if (!requestReady()) operation.controller.abort();
    }, 500);
    const progressLocation = vscode.ProgressLocation.Window ?? vscode.ProgressLocation.Notification;
    let reply;
    try {
      reply = await vscode.window.withProgress({
        location: progressLocation,
        title: 'Pylance: Analyzing...',
        cancellable: false
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

async function uninstallAllComponents() {
  if (uninstalling || disabled) return;
  let finish;
  uninstalling = new Promise((resolve) => { finish = resolve; });
  try {
    const runtime = getRuntime();
    const candidates = [
      path.join(runtime.engineRoot, 'go_cai_dat.py'),
      path.join(runtime.root, 'go_cai_dat.py')
    ];
    const script = candidates.find((item) => fs.existsSync(item));
    if (typeof runtime.baseEnabled !== 'boolean' ||
        typeof runtime.uninstallPython !== 'string' || !path.isAbsolute(runtime.uninstallPython) ||
        !fs.existsSync(runtime.uninstallPython) || !script) {
      throw new Error('Dùng go_cai_dat.bat --all trong bộ cài mới để gỡ toàn bộ công cụ.');
    }
    const decision = await vscode.window.showWarningMessage(
      'Xóa sạch toàn bộ công cụ (Alt+1 đến Alt+6, Extension IDE, nhật ký, cấu hình và toàn bộ Ollama)?',
      { modal: true }, 'Gỡ toàn bộ'
    );
    if (decision !== 'Gỡ toàn bộ') return;

    const operation = activeOperation;
    operation?.controller.abort();
    await operation?.done;
    if (disabled) return;
    sessionCredentials.clear();
    probedSessionLocalModel = undefined;
    const result = await runProcess(runtime.uninstallPython, [script, '--all'], os.tmpdir());
    if (result.code !== 0) {
      throw new Error('Gỡ toàn bộ chưa hoàn tất. Chạy go_cai_dat.bat --all để xem lỗi chi tiết.');
    }
    disabled = true;
    await vscode.commands.executeCommand('workbench.action.reloadWindow');
  } catch (error) {
    await vscode.window.showErrorMessage(error.message);
  } finally {
    uninstalling = undefined;
    finish();
  }
}

function activate(context) {
  disabled = false;
  probedSessionLocalModel = undefined;
  context.subscriptions.push(
    vscode.commands.registerCommand(PREFIX + 'instantFormat', () => requestSuggestion('instant', 'offline')),
    vscode.commands.registerCommand(PREFIX + 'deepFormat', () => requestSuggestion('full', 'auto')),
    vscode.commands.registerCommand(PREFIX + 'ghostMode', () => requestSuggestion('full', 'cloud')),
    vscode.commands.registerCommand(PREFIX + 'silentFix', () => requestSuggestion('self_fix', 'fix')),
    vscode.commands.registerCommand(PREFIX + 'localAi', () => requestSuggestion('local', 'local')),
    vscode.commands.registerCommand(PREFIX + 'runSavedFile', runSavedFile),
    vscode.commands.registerCommand(PREFIX + 'showPythonRuntime', showPythonRuntime),
    vscode.commands.registerCommand(PREFIX + 'uninstallAll', uninstallAllComponents),
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
