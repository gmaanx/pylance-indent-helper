// Run with: node --test tests/test_extension_uninstall.js
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const entry = path.resolve(__dirname, '../shells/vscode_ext/src/extension.js');
const source = fs.readFileSync(entry, 'utf8');

function harness({ scriptMissing = false, noEditor = false } = {}) {
  const localAppData = path.resolve('test-profile');
  const engineRoot = path.join(localAppData, 'Programs', 'PylanceHelper');
  const cli = path.join(engineRoot, 'core_engine', 'cli_entry.py');
  const files = new Set([entry, cli]);
  if (!scriptMissing) files.add(path.join(engineRoot, 'go_cai_dat.py'));
  const commands = new Map();
  const children = [];
  const edits = [];
  const errors = [];
  const info = [];
  const clipboard = [];
  const intervals = [];
  class Position { constructor(line, character) { this.line = line; this.character = character; } }
  class Range { constructor(start, end) { this.start = start; this.end = end; } }
  const editor = {
    selection: { isEmpty: true },
    document: {
      lineCount: 1,
      getText: () => '# sample request',
      lineAt: () => ({ range: { end: new Position(0, 16) } })
    },
    edit: async (callback) => {
      callback({ insert: (_pos, text) => edits.push(text), replace: (_range, text) => edits.push(text) });
      return true;
    }
  };
  const vscode = {
    Position, Range, StatusBarAlignment: { Right: 1 },
    window: {
      activeTextEditor: noEditor ? null : editor,
      createStatusBarItem: () => ({ show() {}, dispose() {} }),
      showInformationMessage: async (message) => { info.push(message); },
      showErrorMessage: async (message) => { errors.push(message); }
    },
    env: { clipboard: { writeText: async (text) => clipboard.push(text) } },
    commands: {
      registerCommand: (name, callback) => { commands.set(name, callback); return { dispose() {} }; },
      executeCommand: async () => {}
    }
  };
  const sandbox = {
    module: { exports: {} }, __filename: entry, __dirname: path.dirname(entry),
    process: { env: { LOCALAPPDATA: localAppData } },
    setInterval: (callback) => { intervals.push(callback); return intervals.length; },
    clearInterval() {}, setTimeout() {},
    require: (name) => {
      if (name === 'vscode') return vscode;
      if (name === 'path') return path;
      if (name === 'os') return { tmpdir: () => path.resolve('test-temp') };
      if (name === 'fs') return { existsSync: (file) => files.has(file) };
      if (name === 'child_process') return { spawn: (_exe, args, options) => {
        const child = new EventEmitter();
        Object.assign(child, {
          args, options, stdout: new EventEmitter(), stderr: new EventEmitter(),
          stdin: { write() {}, end() {} },
          kill() { child.killed = true; }
        });
        children.push(child);
        return child;
      } };
      throw new Error(`Unexpected module: ${name}`);
    }
  };
  vm.runInNewContext(source, sandbox, { filename: entry });
  sandbox.module.exports.activate({ subscriptions: [] });
  return {
    files, cli, engineRoot, children, edits, errors, info, clipboard, intervals,
    run: (name) => commands.get('pylanceIndentHelper.' + name)()
  };
}

const flush = () => new Promise((resolve) => setImmediate(resolve));
const succeeded = (h) => h.edits.some((text) => text.includes('DA GO CAI DAT THANH CONG'));

test('Alt+0 blocks Alt+1 immediately and reports success only after exit 0', async () => {
  const h = harness();
  const uninstall = h.run('uninstallAll');
  assert.equal(h.children.length, 1);
  assert.equal(succeeded(h), false);
  await h.run('instantFormat');
  assert.equal(h.children.length, 1);
  assert.notEqual(h.children[0].options.cwd, h.engineRoot);
  h.children[0].emit('close', 0);
  await uninstall;
  assert.equal(succeeded(h), true);
  assert.equal(h.info.length, 1);
  await h.run('instantFormat');
  assert.equal(h.children.length, 1);
});

test('nonzero exit and spawn errors never report success', async () => {
  for (const failure of ['exit', 'spawn']) {
    const h = harness();
    const uninstall = h.run('uninstallAll');
    if (failure === 'exit') {
      h.children[0].stderr.emit('data', Buffer.from('Access denied'));
      h.children[0].emit('close', 1);
    } else {
      h.children[0].emit('error', new Error('Python not found'));
    }
    await uninstall;
    assert.equal(succeeded(h), false);
    assert.equal(h.errors.length, 1);
    assert.equal(h.info.length, 0);
  }
});

test('missing uninstall script gives an error', async () => {
  const h = harness({ scriptMissing: true });
  await h.run('uninstallAll');
  assert.equal(h.children.length, 0);
  assert.equal(succeeded(h), false);
  assert.match(h.errors[0], /Khong tim thay/);
});

test('uninstall also runs when no editor is open', async () => {
  const h = harness({ noEditor: true });
  const uninstall = h.run('uninstallAll');
  h.children[0].emit('close', 0);
  await uninstall;
  assert.equal(h.errors.length, 0);
  assert.equal(h.info.length, 1);
});

test('external uninstall stops commands without falling back to source', async () => {
  for (const removed of ['engine', 'extension', 'marker']) {
    const h = harness();
    h.files.add(path.join('D:\\UEH\\ai\\midtermtool', 'core_engine', 'cli_entry.py'));
    if (removed === 'engine') h.files.delete(h.cli);
    if (removed === 'extension') h.files.delete(entry);
    if (removed === 'marker') h.files.add(path.join(h.engineRoot, '.uninstalling'));
    await h.run('instantFormat');
    assert.equal(h.children.length, 0);
    assert.equal(h.edits.length, 0);
  }
});

test('late engine results cannot paste code or restart typing after uninstall', async () => {
  for (const command of ['instantFormat', 'ghostMode']) {
    const h = harness();
    const pending = h.run(command);
    await flush();
    assert.equal(h.children.length, 1);
    const engine = h.children[0];
    h.files.add(path.join(h.engineRoot, '.uninstalling'));
    h.intervals[0]();
    assert.equal(engine.killed, true);
    const editCount = h.edits.length;
    engine.stdout.emit('data', Buffer.from(JSON.stringify({ code: 'late code', verified_ok: true })));
    engine.emit('close', 0);
    await pending;
    assert.equal(h.edits.length, editCount);
    assert.equal(h.clipboard.length, 0);
  }
});
