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
  missingUninstaller = false
} = {}) {
  const localAppData = path.resolve('test-profile');
  const engineRoot = path.join(localAppData, 'Programs', 'PylanceHelper');
  const cli = path.join(engineRoot, 'core_engine', 'cli_entry.py');
  const runtimePath = path.join(engineRoot, 'runtime.json');
  const marker = path.join(engineRoot, '.uninstalling');
  const python = path.join(engineRoot, '.venv', 'Scripts', 'python.exe');
  const uninstallPython = path.resolve('system-python.exe');
  const uninstallScript = path.join(engineRoot, 'go_cai_dat.py');
  const files = new Set([entry, cli, runtimePath, python, uninstallPython]);
  if (!missingUninstaller) files.add(uninstallScript);

  const children = [];
  const edits = [];
  const diffs = [];
  const notices = [];
  const contexts = [];
  const prompts = [];
  const timers = new Set();
  const commands = new Map();
  const state = {
    apply: undefined,
    send: undefined,
    uninstall: undefined,
    confirmPreview: undefined
  };
  let previewProvider;
  let uriIndex = 0;
  const uri = (scheme, pathname) => ({ scheme, toString: () => scheme + ':' + pathname });
  const document = {
    uri: uri('file', '/test.py'),
    fileName: 'test.py',
    languageId: 'python',
    eol: 2,
    version: 1,
    isClosed: false,
    offsetAt: (position) => position,
    positionAt: (offset) => offset,
    getText: () => text
  };
  const [start, end] = selected || [0, 0];
  const editor = {
    document,
    selection: { isEmpty: start === end, start, end },
    get selections() { return [this.selection]; }
  };
  const disposable = { dispose() {} };
  const vscode = {
    Range: class Range {
      constructor(start, end) {
        this.start = start;
        this.end = end;
      }
    },
    WorkspaceEdit: class WorkspaceEdit {
      replace(target, range, code) {
        this.change = { target, range, code };
      }
    },
    Uri: { from: ({ scheme, path: pathname }) => uri(scheme, pathname) },
    EndOfLine: { CRLF: 2 },
    ProgressLocation: { Notification: 1 },
    workspace: {
      registerTextDocumentContentProvider: (_scheme, provider) => {
        previewProvider = provider;
        return disposable;
      },
      onDidCloseTextDocument: () => disposable,
      applyEdit: async (edit) => {
        edits.push(edit.change);
        return true;
      }
    },
    window: {
      activeTextEditor: noEditor ? undefined : editor,
      showInformationMessage: async (message, action) => {
        notices.push({ kind: 'info', message });
        return action === 'Áp dụng' && state.confirmPreview ? state.confirmPreview() : state.apply;
      },
      showWarningMessage: async (message, options, action) => {
        notices.push({ kind: 'warning', message, options });
        if (action === 'Gửi') return state.send;
        if (action === 'Gỡ cài đặt') return state.uninstall;
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
        if (name === 'vscode.diff') {
          const [original, proposed, title] = args;
          diffs.push({
            original: previewProvider.provideTextDocumentContent(original),
            proposed: previewProvider.provideTextDocumentContent(proposed),
            title
          });
        }
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
      if (name === 'node:crypto') return { randomUUID: () => String(++uriIndex) };
      if (name === 'node:fs') {
        return {
          existsSync: (file) => files.has(file),
          readFileSync(file) {
            assert.equal(file, runtimePath);
            if (!files.has(file)) throw new Error('missing runtime');
            return JSON.stringify({ engineRoot, python, uninstallPython });
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
    state, document, editor, files, cli, runtimePath, marker, engineRoot, uninstallPython,
    children, edits, diffs, notices, contexts, prompts, timers, extension,
    run: (name) => commands.get('pylanceIndentHelper.' + name)()
  };
}

function finish(child, code = 'print("Đáp án")', options = {}) {
  child.stdout.emit('data', JSON.stringify({ code, validation_status: 'verified', ...options }));
  child.emit('close', 0);
}

test('offline selection uses only selected input, previews whole diff, and edits selection only on Apply', async () => {
  const text = 'before\r\n# selected\r\nafter';
  const start = text.indexOf('#');
  const end = text.indexOf('\r\nafter');
  const h = harness({ text, selected: [start, end] });
  let apply;
  h.state.confirmPreview = () => new Promise((resolve) => { apply = resolve; });
  const pending = h.run('instantFormat');
  await flush();
  assert.deepEqual(JSON.parse(h.children[0].input), {
    text: '# selected', mode: 'instant', verify: true, allow_cloud: false, allow_local: false
  });
  finish(h.children[0], 'x = 1\nprint(x)');
  await flush();
  assert.equal(h.diffs[0].original, text);
  assert.equal(h.diffs[0].proposed, 'before\r\nx = 1\r\nprint(x)\r\nafter');
  assert.equal(h.edits.length, 0);
  apply('Áp dụng');
  await pending;
  await flush();
  assert.equal(h.edits.length, 1);
  assert.equal(h.edits[0].range.start, start);
  assert.equal(h.edits[0].range.end, end);
});

test('a changed document version while processing drops the result', async () => {
  const h = harness();
  const pending = h.run('deepFormat');
  await flush();
  h.document.version++;
  finish(h.children[0]);
  await pending;
  assert.equal(h.edits.length, 0);
  assert.equal(h.diffs.length, 0);
  assert.match(h.notices.at(-1).message, /đã thay đổi/);
});

test('changing the selection after preview prevents Apply', async () => {
  const h = harness({ selected: [0, 3] });
  h.state.confirmPreview = () => {
    h.editor.selection = { isEmpty: false, start: 0, end: 2 };
    return 'Áp dụng';
  };
  const pending = h.run('instantFormat');
  await flush();
  finish(h.children[0]);
  await pending;
  await flush();
  assert.equal(h.diffs.length, 1);
  assert.equal(h.edits.length, 0);
  assert.match(h.notices.at(-1).message, /xem trước đã hết hiệu lực/);
});

test('an older preview cannot apply after the user starts a new request', async () => {
  const h = harness();
  let applyOld;
  h.state.confirmPreview = () => new Promise((resolve) => { applyOld = resolve; });
  const first = h.run('instantFormat');
  await flush();
  finish(h.children[0]);
  await first;
  h.state.confirmPreview = undefined;
  const second = h.run('deepFormat');
  await flush();
  assert.equal(h.children.length, 2);
  applyOld('Áp dụng');
  finish(h.children[1]);
  await second;
  await flush();
  assert.equal(h.edits.length, 0);
  assert.equal(h.diffs.length, 2);
});

test('cancel and external removal prevent late results from opening a preview', async () => {
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
    assert.equal(h.diffs.length, 0);
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
  assert.equal(h.diffs.length, 0);
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

test('uninstall works without an editor and reports success only after exit 0', async () => {
  const h = harness({ noEditor: true });
  await h.run('uninstallAll');
  assert.equal(h.children.length, 0);
  h.state.uninstall = 'Gỡ cài đặt';
  const pending = h.run('uninstallAll');
  await flush();
  assert.equal(h.children.length, 1);
  assert.equal(h.children[0].executable, h.uninstallPython);
  assert.notEqual(h.children[0].options.cwd, h.engineRoot);
  assert.ok(!h.notices.some((notice) => notice.message.startsWith('Đã gỡ')));
  h.children[0].emit('close', 0);
  await pending;
  assert.match(h.notices.at(-1).message, /Đã gỡ/);
  assert.equal(h.edits.length, 0);
});

test('failed or unavailable uninstall names the manual fallback', async () => {
  for (const missingUninstaller of [true, false]) {
    const h = harness({ missingUninstaller });
    h.state.uninstall = 'Gỡ cài đặt';
    const pending = h.run('uninstallAll');
    await flush();
    if (!missingUninstaller) h.children[0].emit('close', 1);
    await pending;
    assert.equal(h.notices.at(-1).kind, 'error');
    assert.match(h.notices.at(-1).message, /go_cai_dat\.bat/);
    assert.equal(h.edits.length, 0);
  }
});
