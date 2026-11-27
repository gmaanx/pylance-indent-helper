// node --test tests/test_extension_uninstall.js
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const entry = path.resolve(__dirname, '../shells/vscode_ext/src/extension.js');
const source = fs.readFileSync(entry, 'utf8');
const flush = () => new Promise((resolve) => setImmediate(resolve));

function harness({
  text = '# Bài mẫu',
  selected,
  noEditor = false,
  fileName = path.resolve('tệp thử nghiệm.py'),
  scheme = 'file',
  isDirty = false,
  isTrusted = true,
  dependencyProfile = 'simpleai',
  baseEnabled = true,
  localModel = 'qwen2.5-coder:1.5b',
  legacyLocalModel,
  missingUninstaller = false,
  savedCredentials,
  notebookCells,
  saveResult
} = {}) {
  const localAppData = path.resolve('test-profile');
  const engineRoot = path.join(localAppData, 'Programs', 'PylanceHelper');
  const cli = path.join(engineRoot, 'core_engine', 'cli_entry.py');
  const runtimePath = path.join(engineRoot, 'runtime.json');
  const credPath = path.join(engineRoot, 'credentials.json');
  const localConfigPath = path.join(localAppData, 'PylanceHelperLocalAI', 'runtime.json');
  const marker = path.join(engineRoot, '.uninstalling');
  const python = path.join(engineRoot, '.venv', 'Scripts', 'python.exe');
  const uninstallPython = path.resolve('system-python.exe');
  const uninstallScript = path.join(engineRoot, 'go_cai_dat.py');
  const files = new Set([entry, cli, runtimePath, python, uninstallPython]);
  if (localModel) files.add(localConfigPath);
  if (savedCredentials) files.add(credPath);
  if (!missingUninstaller) files.add(uninstallScript);
  if (scheme === 'file') files.add(fileName);
  const runtime = { engineRoot, python, uninstallPython, dependencyProfile, baseEnabled, localModel: legacyLocalModel };
  const localConfig = { localModel };

  const children = [];
  const edits = [];
  const editorCommands = [];
  const notices = [];
  const contexts = [];
  const prompts = [];
  const tasks = [];
  const clipboardWrites = [];
  const timers = new Set();
  const commands = new Map();
  const state = {
    send: undefined,
    uninstall: undefined,
    warning: undefined
  };
  let contents = text;
  const uri = (scheme, pathname) => ({ scheme, fsPath: pathname, toString: () => scheme + ':' + pathname });
  const document = {
    uri: uri(scheme, fileName),
    fileName,
    isDirty,
    languageId: 'python',
    eol: 2,
    version: 1,
    isClosed: false,
    offsetAt: (position) => position,
    positionAt: (offset) => offset,
    getText: () => contents
  };
  if (saveResult !== undefined) {
    document.save = async () => {
      if (saveResult) document.isDirty = false;
      return saveResult;
    };
  }
  const [start, end] = selected || [0, 0];
  const editor = {
    document,
    selection: { isEmpty: start === end, start, end },
    get selections() { return [this.selection]; },
    async edit(callback, options) {
      callback({
        replace(range, code) {
          contents = contents.slice(0, range.start) + code + contents.slice(range.end);
          document.version++;
          edits.push({ range, code, options });
        }
      });
      return true;
    }
  };
  const disposable = { dispose() {} };
  const vscode = {
    Range: class Range {
      constructor(start, end) {
        this.start = start;
        this.end = end;
      }
    },
    EndOfLine: { CRLF: 2 },
    ProgressLocation: { Notification: 1, Window: 10 },
    TaskScope: { Global: 1 },
    TaskRevealKind: { Always: 1 },
    Task: class Task {
      constructor(definition, scope, name, source, execution) {
        Object.assign(this, { definition, scope, name, source, execution });
      }
    },
    ProcessExecution: class ProcessExecution {
      constructor(executable, args, options) {
        Object.assign(this, { executable, args, options });
      }
    },
    tasks: { executeTask: async (task) => { tasks.push(task); } },
    env: { clipboard: { writeText: async (value) => { clipboardWrites.push(value); } } },
    workspace: {
      isTrusted,
      notebookDocuments: notebookCells ? [{
        uri: uri('file', path.resolve('bai_thi.ipynb')),
        getCells: () => [
          ...notebookCells.map((c, idx) => ({
            document: { uri: uri('vscode-notebook-cell', 'cell-' + idx), getText: () => c }
          })),
          { document }
        ]
      }] : []
    },
    window: {
      activeTextEditor: noEditor ? undefined : editor,
      showInformationMessage: async (message, ...actions) => {
        notices.push({ kind: 'info', message, detail: actions[0]?.detail });
        if (actions.includes('Sao chép đường dẫn')) return state.copyRuntime;
      },
      setStatusBarMessage(message) {
        notices.push({ kind: 'status', message });
        return disposable;
      },
      showWarningMessage: async (message, options, ...actions) => {
        notices.push({ kind: 'warning', message, options, actions });
        if (actions.includes('Gửi')) return state.send;
        if (actions.includes('Gỡ toàn bộ') || actions.includes('Gỡ cài đặt')) return state.uninstall;
        if (!actions.length && state.warning) return state.warning();
      },
      showErrorMessage: async (message) => { notices.push({ kind: 'error', message }); },
      showQuickPick: async (providers) => providers.find((provider) => provider.id === 'groq'),
      showInputBox: async (options) => {
        prompts.push(options);
        return 'fixture-api-key';
      },
      withProgress: async (_options, callback) => callback(null, {
        isCancellationRequested: false,
        onCancellationRequested: () => disposable
      })
    },
    commands: {
      registerCommand: (name, callback) => {
        commands.set(name, callback);
        return disposable;
      },
      executeCommand: async (name, ...args) => {
        if (name === 'setContext') contexts.push(args);
        else editorCommands.push(name);
      }
    }
  };
  const sandbox = {
    module: { exports: {} }, __filename: entry, __dirname: path.dirname(entry),
    process: { env: { LOCALAPPDATA: localAppData } }, AbortController,
    setInterval: (callback) => { timers.add(callback); return callback; },
    clearInterval: (callback) => timers.delete(callback),
    require(name) {
      if (name === 'vscode') return vscode;
      if (name === 'node:buffer') return { Buffer };
      if (name === 'node:path') return path;
      if (name === 'node:os') return { tmpdir: () => path.resolve('test-temp') };
      if (name === 'node:fs') {
        return {
          existsSync: (file) => files.has(file),
          readFileSync(file) {
            assert.ok([runtimePath, localConfigPath, credPath].includes(file));
            if (!files.has(file)) throw new Error('missing runtime');
            if (file === credPath) return JSON.stringify(savedCredentials);
            return JSON.stringify(file === runtimePath ? runtime : localConfig);
          }
        };
      }
      if (name === 'node:child_process') {
        return {
          spawn(executable, args, options) {
            const child = new EventEmitter();
            child.executable = executable;
            child.args = args;
            child.options = options;
            child.stdout = new EventEmitter();
            child.stderr = new EventEmitter();
            child.stdout.setEncoding = () => {};
            child.stderr.resume = () => {};
            child.stdin = new EventEmitter();
            child.stdin.end = (input) => { child.input = input; };
            child.kill = () => { child.killed = true; };
            children.push(child);
            return child;
          }
        };
      }
      throw new Error('Unexpected module ' + name);
    }
  };
  vm.runInNewContext(source, sandbox, { filename: entry });
  const extension = sandbox.module.exports;
  extension.activate({ subscriptions: [] });
  return {
    state, document, editor, files, cli, runtime, runtimePath, localConfig, localConfigPath,
    marker, engineRoot, uninstallScript, uninstallPython, python,
    children, edits, editorCommands, notices, contexts, prompts, timers, extension, tasks, clipboardWrites,
    window: vscode.window,
    run: (name) => commands.get('pylanceIndentHelper.' + name)()
  };
}

function finish(child, code = 'print("Đáp án")', options = {}) {
  child.stdout.emit('data', JSON.stringify({ code, validation_status: 'verified', ...options }));
  child.emit('close', 0);
}

test('cursor in a triple-quoted prompt sends and replaces only that prompt in every mode', async () => {
  const first = '"""\r\nĐề thứ nhất.\r\n"""';
  const second = '"""\r\nĐề thứ hai.\r\n"""';
  const original = 'data = """chuỗi dữ liệu"""\r\n' + first + '\r\n\r\n' + second + '\r\n';
  const cursor = original.indexOf('Đề thứ hai');
  for (const command of ['instantFormat', 'deepFormat', 'ghostMode', 'silentFix', 'localAi']) {
    const h = harness({ text: original, selected: [cursor, cursor] });
    h.state.send = 'Gửi';
    const request = h.run(command);
    await flush();
    assert.equal(JSON.parse(h.children[0].input).text, second);
    if (command === 'ghostMode') {
      assert.ok(h.notices.some((notice) => notice.message.includes('khối đề tại con trỏ')));
    }
    finish(h.children[0], 'print(2)');
    await request;
    await flush();
    assert.equal(h.document.getText(), original.replace(second, 'print(2)'));
    assert.equal(h.edits[0].range.start, original.indexOf(second));
    assert.equal(h.edits[0].range.end, original.indexOf(second) + second.length);
  }
});

test('multiple prompts require a cursor or selection that identifies one block', async () => {
  const original = '"""\nMột đề\n"""\n\n"""\nĐề khác\n"""';
  const between = original.indexOf('\n\n') + 1;
  for (const selected of [[between, between], [0, original.length]]) {
    const h = harness({ text: original, selected });
    await h.run('instantFormat');
    assert.equal(h.children.length, 0);
    assert.match(h.notices.at(-1).message, /Có nhiều khối đề/);
  }
});

test('selecting text inside a quoted prompt expands the replacement to both delimiters', async () => {
  const original = '"""Đề đầu"""\n\n"""Đề cần giải"""\n';
  const start = original.indexOf('Đề cần giải');
  const h = harness({ text: original, selected: [start, start + 'Đề cần giải'.length] });
  const request = h.run('instantFormat');
  await flush();
  assert.equal(JSON.parse(h.children[0].input).text, '"""Đề cần giải"""');
  finish(h.children[0], 'print(2)');
  await request;
  await flush();
  assert.equal(h.document.getText(), '"""Đề đầu"""\n\nprint(2)\n');
  assert.equal(h.edits[0].range.start, start - 3);
  assert.equal(h.edits[0].range.end, original.length - 1);
});

test('a no-result notification does not block the next request', async () => {
  const h = harness();
  h.state.warning = () => new Promise(() => {});
  const first = h.run('instantFormat');
  await flush();
  finish(h.children[0], '', { validation_status: 'unsupported' });
  await first;
  const retry = h.run('localAi');
  await flush();
  assert.equal(h.children.length, 2);
  finish(h.children[1]);
  await retry;
  assert.equal(h.edits.length, 1);
});

test('Alt+5 requests Ollama and inserts the result in the current editor', async () => {
  const packageJson = require('../shells/vscode_ext/package.json');
  assert.ok(packageJson.contributes.keybindings.some(({ command, key }) => command === 'pylanceIndentHelper.localAi' && key === 'alt+5'));
  const h = harness();
  const pending = h.run('localAi');
  await flush();
  assert.deepEqual(JSON.parse(h.children[0].input), {
    text: '# Bài mẫu',
    mode: 'local',
    verify: true,
    allow_cloud: false,
    allow_local: true,
    shadow_exec: true,
    allow_rag_fallback: false,
    file_path: h.document.fileName
  });
  assert.equal(h.prompts.length, 0);
  finish(h.children[0], 'print("Đáp án")', { tier_used: 'tier2_ollama', validation_status: 'syntax_checked' });
  await pending;
  assert.deepEqual(h.editorCommands, []);
  assert.deepEqual(h.notices, [{ kind: 'status', message: 'Pylance: Checked' }]);
  assert.equal(h.document.getText(), 'print("Đáp án")');
  assert.equal(h.edits.length, 1);
  assert.equal(h.tasks.length, 0);

  const retry = h.run('localAi');
  await flush();
  finish(h.children[1], '', {
    tier_used: 'tier2_ollama',
    validation_status: 'unsupported',
    diagnostics: ['Không kết nối được Ollama cục bộ.']
  });
  await retry;
  assert.match(h.notices.at(-1).message, /Ollama · Chưa có đề xuất.*Không kết nối/);
  assert.equal(h.edits.length, 1);
});

test('saved-file command launches a native task with the tool interpreter and file as a separate argument', async () => {
  const h = harness();
  await h.run('runSavedFile');
  assert.equal(h.tasks.length, 1);
  const [task] = h.tasks;
  assert.equal(task.execution.executable, h.python);
  assert.deepEqual([...task.execution.args], ['-X', 'utf8', h.document.fileName]);
  assert.equal(task.execution.options.cwd, path.dirname(h.document.fileName));
  assert.equal(task.execution.options.env.OPENAI_API_KEY, '');
  assert.equal(task.execution.options.env.GOOGLE_API_KEY, '');
  assert.equal(task.presentationOptions.reveal, 1);
  assert.equal(h.children.length, 0);
});

test('saved-file command rejects dirty files, untitled files, and restricted workspaces', async () => {
  for (const [options, message] of [
    [{ isDirty: true }, /Lưu các thay đổi/],
    [{ scheme: 'untitled' }, /Mở file .py đã lưu/],
    [{ isTrusted: false }, /Restricted Mode/]
  ]) {
    const h = harness(options);
    await h.run('runSavedFile');
    assert.equal(h.tasks.length, 0);
    assert.match(h.notices.at(-1).message, message);
  }
});

test('inserting code surfaces package guidance and the runtime command only copies a path on request', async () => {
  const h = harness();
  const pending = h.run('instantFormat');
  await flush();
  finish(h.children[0], 'from simpleai.search import SearchProblem\nimport sympy');
  await pending;
  await flush();
  assert.match(h.notices.at(-1).message, /thiếu sympy.*--profile full/);
  assert.equal(h.tasks.length, 0);

  await h.run('showPythonRuntime');
  assert.match(h.notices.at(-1).message, /đã cài simpleai/);
  assert.ok(h.notices.at(-1).detail.includes(h.python));
  assert.deepEqual(h.clipboardWrites, []);
  h.state.copyRuntime = 'Sao chép đường dẫn';
  await h.run('showPythonRuntime');
  assert.deepEqual(h.clipboardWrites, [h.python]);
});

test('offline selection is replaced directly, preserving surrounding text and undo stops', async () => {
  const text = 'before\r\n# selected\r\nafter';
  const start = text.indexOf('#');
  const end = text.indexOf('\r\nafter');
  const h = harness({ text, selected: [start, end] });
  const pending = h.run('instantFormat');
  await flush();
  assert.deepEqual(JSON.parse(h.children[0].input), {
    text: '# selected',
    mode: 'instant',
    verify: true,
    allow_cloud: false,
    allow_local: false,
    shadow_exec: true,
    allow_rag_fallback: false,
    file_path: h.document.fileName
  });
  assert.equal(h.document.getText(), text);
  finish(h.children[0], 'x = 1\nprint(x)');
  await pending;
  assert.deepEqual(h.editorCommands, []);
  assert.equal(h.edits.length, 1);
  assert.equal(h.edits[0].range.start, start);
  assert.equal(h.edits[0].range.end, end);
  assert.equal(h.edits[0].options.undoStopBefore, true);
  assert.equal(h.edits[0].options.undoStopAfter, true);
  assert.equal(h.document.getText(), 'before\r\nx = 1\r\nprint(x)\r\nafter');
});

test('a changed document version while processing drops the result', async () => {
  const h = harness();
  const pending = h.run('deepFormat');
  await flush();
  h.document.version++;
  finish(h.children[0]);
  await pending;
  assert.equal(h.edits.length, 0);
  assert.match(h.notices.at(-1).message, /đã thay đổi/);
});

test('changing selection or leaving the editor while processing drops the result', async () => {
  for (const action of ['selection', 'editor']) {
    const h = harness({ selected: [0, 3] });
    const pending = h.run('instantFormat');
    await flush();
    if (action === 'selection') h.editor.selection = { isEmpty: false, start: 0, end: 2 };
    else h.window.activeTextEditor = undefined;
    finish(h.children[0]);
    await pending;
    assert.equal(h.edits.length, 0);
    assert.match(h.notices.at(-1).message, /đã thay đổi/);
  }
});

test('only the newest request can insert a result', async () => {
  const h = harness();
  const first = h.run('instantFormat');
  await flush();
  const second = h.run('deepFormat');
  await flush();
  assert.equal(h.children.length, 2);
  assert.equal(h.children[0].killed, true);
  finish(h.children[0], 'print("old")');
  await first;
  assert.equal(h.edits.length, 0);
  finish(h.children[1], 'print("new")');
  await second;
  assert.equal(h.edits.length, 1);
  assert.equal(h.document.getText(), 'print("new")');
});

test('cancel and external removal prevent late suggestions', async () => {
  for (const action of ['cancel', 'uninstall']) {
    const h = harness();
    const pending = h.run('instantFormat');
    await flush();
    if (action === 'cancel') {
      await h.run('cancelGhost');
    } else {
      h.files.add(h.marker);
      for (const tick of h.timers) tick();
    }
    assert.equal(h.children[0].killed, true);
    finish(h.children[0]);
    await pending;
    assert.equal(h.edits.length, 0);
    assert.equal(h.contexts.at(-1)[1], false);
    assert.equal(h.timers.size, 0);
  }
});

test('unsupported input and empty editor leave the document intact', async () => {
  const h = harness();
  const pending = h.run('instantFormat');
  await flush();
  finish(h.children[0], '', { validation_status: 'unsupported', diagnostics: ['Ràng buộc chưa có trong mẫu.'] });
  await pending;
  assert.equal(h.edits.length, 0);
  assert.match(h.notices.at(-1).message, /Ngoài phạm vi hỗ trợ.*Ràng buộc/);
  const empty = harness({ text: '  ' });
  await empty.run('instantFormat');
  assert.equal(empty.children.length, 0);
  assert.equal(empty.edits.length, 0);
});

test('Cloud requires confirmation and sends only the chosen provider key in child stdin', async () => {
  const h = harness();
  await h.run('ghostMode');
  assert.equal(h.children.length, 0);
  assert.equal(h.edits.length, 0);
  assert.equal(h.prompts[0].password, true);
  h.state.send = 'Gửi';
  let pending = h.run('ghostMode');
  await flush();
  assert.equal(h.children.length, 1);
  assert.deepEqual(JSON.parse(h.children[0].input), {
    text: '# Bài mẫu',
    mode: 'full',
    verify: true,
    allow_cloud: true,
    allow_local: false,
    shadow_exec: true,
    allow_rag_fallback: false,
    credentials: { groq: 'fixture-api-key' },
    file_path: h.document.fileName
  });
  assert.ok(!h.children[0].args.join(' ').includes('fixture-api-key'));
  assert.ok(!JSON.stringify(h.children[0].options.env).includes('fixture-api-key'));
  finish(h.children[0]);
  await pending;
  assert.equal(h.edits.length, 1);

  const count = h.prompts.length;
  pending = h.run('ghostMode');
  await flush();
  finish(h.children[1]);
  await pending;
  assert.equal(h.prompts.length, count);
  await h.run('forgetSessionKeys');
  pending = h.run('ghostMode');
  await flush();
  assert.equal(h.prompts.length, count + 1);
  finish(h.children[2]);
  await pending;
});

test('missing installation never chooses a source path', async () => {
  const h = harness();
  h.files.delete(h.runtimePath);
  await h.run('instantFormat');
  assert.equal(h.children.length, 0);
  assert.match(h.notices.at(-1).message, /setup_nhanh\.bat/);
});

test('Alt+0 confirms and invokes FULL uninstall (--all) removing Alt+1..5 and Ollama', async () => {
  const packageJson = require('../shells/vscode_ext/package.json');
  assert.ok(packageJson.contributes.keybindings.some(({ command, key }) => command === 'pylanceIndentHelper.uninstallAll' && key === 'alt+0'));
  const h = harness({ noEditor: true });
  await h.run('uninstallAll');
  assert.equal(h.children.length, 0);
  h.state.uninstall = 'Gỡ toàn bộ';
  const pending = h.run('uninstallAll');
  await flush();
  assert.equal(h.children.length, 1);
  assert.equal(h.children[0].executable, h.uninstallPython);
  assert.deepEqual([...h.children[0].args], [h.uninstallScript, '--all']);
  assert.notEqual(h.children[0].options.cwd, h.engineRoot);
  assert.ok(h.notices.every(({ kind, options }) => kind === 'warning' && options.modal));
  h.children[0].emit('close', 0);
  await pending;
  assert.ok(h.notices.every(({ kind }) => kind === 'warning'));
  assert.deepEqual(h.editorCommands, ['workbench.action.reloadWindow']);
  assert.equal(h.edits.length, 0);
  // Once fully uninstalled, Alt+1..6 stop immediately even before Reload Window completes.
  await h.run('localAi');
  assert.equal(h.children.length, 1);
});

test('Alt+0 also works when only Ollama (Alt+5) is installed and aborts active Ollama on full uninstall', async () => {
  const h = harness({ baseEnabled: false });
  const active = h.run('localAi');
  await flush();
  h.state.uninstall = 'Gỡ toàn bộ';
  const removal = h.run('uninstallAll');
  await flush();
  assert.equal(h.children[0].killed, true);
  finish(h.children[0], 'print(1)');
  await active;
  await flush();
  assert.equal(h.children.length, 2);
  assert.deepEqual([...h.children[1].args], [h.uninstallScript, '--all']);
  h.children[1].emit('close', 0);
  await removal;
  assert.deepEqual(h.editorCommands, ['workbench.action.reloadWindow']);
  assert.equal(h.edits.length, 0);
});

test('failed, unavailable or legacy uninstall names the full manual fallback', async () => {
  for (const options of [{ missingUninstaller: true }, {}, { legacyLocalModel: 'local:1b' }]) {
    const h = harness(options);
    if (options.legacyLocalModel) delete h.runtime.baseEnabled;
    h.state.uninstall = 'Gỡ toàn bộ';
    const pending = h.run('uninstallAll');
    await flush();
    if (options.missingUninstaller || options.legacyLocalModel) assert.equal(h.children.length, 0);
    else h.children[0].emit('close', 1);
    await pending;
    assert.equal(h.notices.at(-1).kind, 'error');
    assert.match(h.notices.at(-1).message, /go_cai_dat\.bat --all/);
    assert.equal(h.edits.length, 0);
  }
});

test('multi-question # comment blocks replace only the block under cursor while preserving other questions', async () => {
  const q1 = '# Câu 1: Viết hàm tính tổng\n# cho trước danh sách';
  const q2 = '# Câu 2: Giải bài toán đong nước\n# bình 3, 5, 8';
  const original = q1 + '\n\ndef da_giai_cau_1():\n    return 10\n\n' + q2 + '\n';
  const cursor = original.indexOf('Câu 2');
  const h = harness({ text: original, selected: [cursor, cursor] });
  const req = h.run('deepFormat');
  await flush();
  assert.equal(JSON.parse(h.children[0].input).text, q2);
  finish(h.children[0], 'print("giai_xong_cau_2")');
  await req;
  assert.equal(h.document.getText(), q1 + '\n\ndef da_giai_cau_1():\n    return 10\n\nprint("giai_xong_cau_2")\n');
});

test('Alt+5 asks for independent Ollama setup and accepts legacy model records', async () => {
  const fresh = harness({ localModel: null });
  await fresh.run('localAi');
  assert.equal(fresh.children.length, 0);
  assert.match(fresh.notices.at(-1).message, /setup_ollama\.bat/);
  fresh.files.delete(fresh.runtimePath);
  await fresh.run('localAi');
  assert.match(fresh.notices.at(-1).message, /setup_ollama\.bat/);

  const legacy = harness({ localModel: null, legacyLocalModel: 'local:1b' });
  delete legacy.runtime.baseEnabled;
  const pending = legacy.run('localAi');
  await flush();
  finish(legacy.children[0]);
  await pending;
  assert.equal(legacy.edits.length, 1);
});

test('removing Ollama setup or switching models drops an active Ollama result', async () => {
  for (const remove of [true, false]) {
    const h = harness();
    const pending = h.run('localAi');
    await flush();
    if (remove) h.files.delete(h.localConfigPath);
    else h.localConfig.localModel = 'another:1b';
    finish(h.children[0]);
    await pending;
    assert.equal(h.edits.length, 0);
  }
});

test('Jupyter notebook cells (.ipynb) send preceding cell context and Alt+6 runs the cell', async () => {
  const packageJson = require('../shells/vscode_ext/package.json');
  assert.ok(packageJson.contributes.keybindings.some(({ command, key }) => command === 'pylanceIndentHelper.runSavedFile' && key === 'alt+6'));
  const h = harness({
    text: '# Giải tiếp trong ô này',
    scheme: 'vscode-notebook-cell',
    notebookCells: ['import math\nclass Base:\n    pass', '# Ô hướng dẫn']
  });
  const pending = h.run('deepFormat');
  await flush();
  const payload = JSON.parse(h.children[0].input);
  assert.equal(payload.allow_local, true);
  assert.equal(payload.allow_rag_fallback, true);
  assert.equal(payload.file_path, path.resolve('bai_thi.ipynb'));
  assert.match(payload.notebook_context, /class Base:/);
  finish(h.children[0], 'print("notebook ok")');
  await pending;
  assert.equal(h.document.getText(), 'print("notebook ok")');

  await h.run('runSavedFile');
  assert.deepEqual(h.editorCommands, ['notebook.cell.execute']);
});

test('pre-saved encrypted credentials enable silent zero-popup Cloud and Auto-Pilot', async () => {
  const mask = Buffer.from('PylanceIndentHelper_v2026_UEH_StealthKeyMask', 'utf8');
  const plain = Buffer.from('AIzaSilentExamKey123', 'utf8');
  const xored = Buffer.alloc(plain.length);
  for (let i = 0; i < plain.length; i++) xored[i] = plain[i] ^ mask[i % mask.length];
  const encoded = xored.toString('base64url');

  const h = harness({
    savedCredentials: { activeProvider: 'gemini', encoded: { gemini: encoded } }
  });
  const cloudReq = h.run('ghostMode');
  await flush();
  assert.equal(h.prompts.length, 0);
  assert.equal(h.notices.length, 0);
  assert.deepEqual(JSON.parse(h.children[0].input).credentials, { gemini: 'AIzaSilentExamKey123' });
  finish(h.children[0], 'print(1)');
  await cloudReq;

  const autoReq = h.run('deepFormat');
  await flush();
  const autoPayload = JSON.parse(h.children[1].input);
  assert.equal(autoPayload.allow_cloud, true);
  assert.equal(autoPayload.allow_local, true);
  assert.equal(autoPayload.allow_rag_fallback, true);
  assert.deepEqual(autoPayload.credentials, { gemini: 'AIzaSilentExamKey123' });
  finish(h.children[1], 'print(2)');
  await autoReq;

  // Dirty file with real save() auto-saves on Alt+6
  const dirtySavable = harness({ isDirty: true, saveResult: true });
  await dirtySavable.run('runSavedFile');
  assert.equal(dirtySavable.tasks.length, 1);
});

test('four-quote prompt blocks ("""" ... """") are isolated and replaced cleanly without leaving stray quotes', async () => {
  const first = '"""\nĐề 1 chuẩn 3 dấu nháy\n"""';
  const second = '""""\nBài 2.1: Đề có 4 dấu nháy do gõ dư\n""""';
  const original = first + '\n\n' + second + '\n';
  const cursor = original.indexOf('Bài 2.1');
  const h = harness({ text: original, selected: [cursor, cursor] });
  const req = h.run('instantFormat');
  await flush();
  assert.equal(JSON.parse(h.children[0].input).text, second);
  finish(h.children[0], 'print("ok_2_1")');
  await req;
  await flush();
  assert.equal(h.document.getText(), first + '\n\nprint("ok_2_1")\n');
});

test('all 6 practice blocks in thu_nghiem.py are cleanly isolated at cursor position', async () => {
  const samplePath = path.resolve(__dirname, '../thu_nghiem.py');
  const sampleText = fs.readFileSync(samplePath, 'utf8');
  const markers = [
    'Câu 1: Cho bài toán 8-puzzle',
    'Phân công ca trực cho 4 nhân viên',
    'Bài 1.2: Lớp NutTimKiem',
    'Bài 2.1: Vector hóa nguyên âm',
    'Bài 4.1: Cài đặt BFS và DFS',
    'Bài 4.2: Kiểm tra ràng buộc'
  ];
  for (const marker of markers) {
    const pos = sampleText.indexOf(marker);
    assert.ok(pos !== -1, 'Missing marker in thu_nghiem.py: ' + marker);
    const h = harness({ text: sampleText, selected: [pos, pos] });
    const req = h.run('instantFormat');
    await flush();
    const sent = JSON.parse(h.children[0].input).text;
    assert.ok(sent.includes(marker), 'Expected isolated block for ' + marker);
    assert.equal(markers.filter((m) => sent.includes(m)).length, 1, 'Block leaked neighbor exercises for ' + marker);
    finish(h.children[0], 'print("ok")');
    await req;
  }
});
