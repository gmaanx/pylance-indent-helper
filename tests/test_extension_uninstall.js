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
  missingUninstaller = false
} = {}) {
  const localAppData = path.resolve('test-profile');
  const engineRoot = path.join(localAppData, 'Programs', 'PylanceHelper');
  const cli = path.join(engineRoot, 'core_engine', 'cli_entry.py');
  const runtimePath = path.join(engineRoot, 'runtime.json');
  const localConfigPath = path.join(localAppData, 'PylanceHelperLocalAI', 'runtime.json');
  const marker = path.join(engineRoot, '.uninstalling');
  const python = path.join(engineRoot, '.venv', 'Scripts', 'python.exe');
  const uninstallPython = path.resolve('system-python.exe');
  const uninstallScript = path.join(engineRoot, 'go_cai_dat.py');
  const files = new Set([entry, cli, runtimePath, python, uninstallPython]);
  if (localModel) files.add(localConfigPath);
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
    ProgressLocation: { Notification: 1 },
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
    workspace: { isTrusted },
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
      showWarningMessage: async (message, options, action) => {
        notices.push({ kind: 'warning', message, options });
        if (action === 'Gửi') return state.send;
        if (action === 'Gỡ cài đặt') return state.uninstall;
        if (!action && state.warning) return state.warning();
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
      if (name === 'node:path') return path;
      if (name === 'node:os') return { tmpdir: () => path.resolve('test-temp') };
      if (name === 'node:fs') {
        return {
          existsSync: (file) => files.has(file),
          readFileSync(file) {
            assert.ok([runtimePath, localConfigPath].includes(file));
            if (!files.has(file)) throw new Error('missing runtime');
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
    text: '# Bài mẫu', mode: 'local', verify: true, allow_cloud: false, allow_local: true
  });
  assert.equal(h.prompts.length, 0);
  finish(h.children[0], 'print("Đáp án")', { tier_used: 'tier2_ollama', validation_status: 'syntax_checked' });
  await pending;
  assert.deepEqual(h.editorCommands, []);
  assert.deepEqual(h.notices, [{ kind: 'status', message: 'Đã chèn mã · Ollama · Đã kiểm tra cú pháp' }]);
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
    text: '# selected', mode: 'instant', verify: true, allow_cloud: false, allow_local: false
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
    text: '# Bài mẫu', mode: 'full', verify: true, allow_cloud: true, allow_local: false,
    credentials: { groq: 'fixture-api-key' }
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

test('Alt+0 confirms and invokes only the BASE uninstall without a success notice or reload', async () => {
  const packageJson = require('../shells/vscode_ext/package.json');
  assert.ok(packageJson.contributes.keybindings.some(({ command, key }) => command === 'pylanceIndentHelper.uninstallAll' && key === 'alt+0'));
  const h = harness({ noEditor: true });
  await h.run('uninstallAll');
  assert.equal(h.children.length, 0);
  h.state.uninstall = 'Gỡ cài đặt';
  const pending = h.run('uninstallAll');
  await flush();
  assert.equal(h.children.length, 1);
  assert.equal(h.children[0].executable, h.uninstallPython);
  assert.deepEqual([...h.children[0].args], [h.uninstallScript, '--base-only']);
  assert.notEqual(h.children[0].options.cwd, h.engineRoot);
  assert.ok(h.notices.every(({ kind, options }) => kind === 'warning' && options.modal));
  h.children[0].emit('close', 0);
  await pending;
  assert.ok(h.notices.every(({ kind }) => kind === 'warning'));
  assert.deepEqual(h.editorCommands, []);
  assert.equal(h.edits.length, 0);
});

test('failed, unavailable or legacy uninstall names the BASE manual fallback', async () => {
  for (const options of [{ missingUninstaller: true }, {}, { legacyLocalModel: 'local:1b' }]) {
    const h = harness(options);
    if (options.legacyLocalModel) delete h.runtime.baseEnabled;
    h.state.uninstall = 'Gỡ cài đặt';
    const pending = h.run('uninstallAll');
    await flush();
    if (options.missingUninstaller || options.legacyLocalModel) assert.equal(h.children.length, 0);
    else h.children[0].emit('close', 1);
    await pending;
    assert.equal(h.notices.at(-1).kind, 'error');
    assert.match(h.notices.at(-1).message, /go_cai_dat\.bat --base-only/);
    assert.equal(h.edits.length, 0);
  }
});

test('Alt+0 waits for active Ollama and Alt+5 can use the lean runtime afterward', async () => {
  const h = harness();
  const local = h.run('localAi');
  await flush();
  h.state.uninstall = 'Gỡ cài đặt';
  const removal = h.run('uninstallAll');
  await flush();
  assert.equal(h.children.length, 1);
  assert.equal(h.children[0].killed, undefined);
  finish(h.children[0], 'print(1)');
  await local;
  await flush();
  assert.equal(h.children.length, 2);
  const next = h.run('localAi');
  await flush();
  assert.equal(h.children.length, 2);
  h.runtime.baseEnabled = false;
  h.runtime.python = path.join(h.engineRoot, 'lean-python.exe');
  h.files.add(h.runtime.python);
  h.files.delete(h.python);
  h.children[1].emit('close', 0);
  await removal;
  await flush();
  assert.equal(h.children[2].executable, h.runtime.python);
  finish(h.children[2], 'print(2)');
  await next;
  assert.equal(h.document.getText(), 'print(2)');
  await h.run('deepFormat');
  assert.match(h.notices.at(-1).message, /setup_nhanh\.bat.*phần cơ bản/);
  assert.equal(h.children.length, 3);
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
