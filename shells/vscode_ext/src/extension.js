const vscode = require('vscode');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

let statusBarItem = null;
let ghostTimer = null;
let isGhostStreaming = false;
let activeGhostEditor = null;
let runtimeDisabled = false;
let uninstalling = false;
let installedEngineRoot = null;
const engineProcesses = new Set();

function disableRuntime() {
  runtimeDisabled = true;
  stopGhostMode(false);
  for (const child of engineProcesses) {
    child.kill();
  }
  engineProcesses.clear();
  setStatus('$(circle-slash) Pylance: Disabled');
}

function canRunEngine() {
  if (runtimeDisabled) {
    return false;
  }
  // Giữ nguyên root đã nạp: không quay về mã nguồn sau khi bản cài bị xóa.
  if (!fs.existsSync(__filename) ||
      !fs.existsSync(path.join(installedEngineRoot, 'core_engine', 'cli_entry.py')) ||
      fs.existsSync(path.join(installedEngineRoot, '.uninstalling'))) {
    disableRuntime();
    return false;
  }
  return true;
}

function findEngineRoot() {
  const candidates = [
    path.join(process.env.LOCALAPPDATA || os.tmpdir(), 'Programs', 'PylanceHelper'),
    'D:\\UEH\\ai\\midtermtool',
    path.resolve(__dirname, '..', '..', '..')
  ];
  for (const dir of candidates) {
    if (fs.existsSync(path.join(dir, 'core_engine', 'cli_entry.py'))) {
      return dir;
    }
  }
  return candidates[0];
}

function findPythonExecutable(engineRoot) {
  const candidates = [
    'D:\\UEH\\ai\\.venv\\Scripts\\python.exe',
    path.join(path.dirname(engineRoot), '.venv', 'Scripts', 'python.exe'),
    path.join(engineRoot, '.venv', 'Scripts', 'python.exe'),
    'python'
  ];
  for (const exe of candidates) {
    if (exe === 'python' || fs.existsSync(exe)) {
      return exe;
    }
  }
  return 'python';
}

function setStatus(text, timeoutMs = 0) {
  if (!statusBarItem) {
    return;
  }
  statusBarItem.text = text;
  statusBarItem.show();
  if (timeoutMs > 0) {
    setTimeout(() => {
      if (statusBarItem && !isGhostStreaming && !runtimeDisabled) {
        statusBarItem.text = '$(check) Pylance';
      }
    }, timeoutMs);
  }
}

async function stopGhostMode(appendStoppedComment = false) {
  if (ghostTimer) {
    clearInterval(ghostTimer);
    ghostTimer = null;
  }
  const wasStreaming = isGhostStreaming;
  isGhostStreaming = false;
  if (wasStreaming && appendStoppedComment && activeGhostEditor) {
    try {
      const doc = activeGhostEditor.document;
      const lastLine = doc.lineCount - 1;
      const endPos = doc.lineAt(lastLine).range.end;
      await activeGhostEditor.edit(
        (eb) => {
          eb.insert(endPos, '\n# [Alt+3: Da dung go tu dong theo lenh Esc]\n');
        },
        { undoStopBefore: false, undoStopAfter: false }
      );
    } catch (_e) {
      // ignore
    }
  }
  activeGhostEditor = null;
  setStatus('$(check) Pylance', 2000);
}

async function getOrOpenEditor() {
  if (vscode.window.activeTextEditor) {
    return vscode.window.activeTextEditor;
  }
  if (vscode.window.visibleTextEditors && vscode.window.visibleTextEditors.length > 0) {
    return vscode.window.visibleTextEditors[0];
  }
  const doc = await vscode.workspace.openTextDocument({ language: 'python', content: '' });
  return await vscode.window.showTextDocument(doc);
}

function extractTargetText(editor) {
  const doc = editor.document;
  const sel = editor.selection;
  if (!sel.isEmpty) {
    return {
      text: doc.getText(sel),
      range: new vscode.Range(sel.start, sel.end)
    };
  }
  const fullText = doc.getText();
  const lastLine = Math.max(0, doc.lineCount - 1);
  const fullRange = new vscode.Range(
    new vscode.Position(0, 0),
    doc.lineAt(lastLine).range.end
  );
  return { text: fullText, range: fullRange };
}

function startAutoStreamGhostMode(editor, codeToStream) {
  if (!canRunEngine()) {
    return;
  }
  stopGhostMode(false);
  const normalized = codeToStream.replace(/\r\n/g, '\n');
  let cursorIdx = 0;
  isGhostStreaming = true;
  activeGhostEditor = editor;
  setStatus('$(sync~spin) Pylance: Typing (Esc to stop)...');

  let busyTick = false;
  ghostTimer = setInterval(async () => {
    if (!canRunEngine() || !isGhostStreaming || busyTick) {
      return;
    }
    if (cursorIdx >= normalized.length) {
      await stopGhostMode(false);
      setStatus('$(check) Pylance: Ghost Done', 4000);
      return;
    }
    busyTick = true;
    try {
      // Go 4-6 ky tu moi nhip (18ms) de code chay ra man hinh muot ma, thay ro ngay lap tuc
      let step = 5;
      let chunk = normalized.slice(cursorIdx, cursorIdx + step);
      cursorIdx += chunk.length;

      // Neu gap xuong dong, gom luon khoang trang thut le dau dong tiep theo
      if (chunk.endsWith('\n')) {
        while (cursorIdx < normalized.length && normalized[cursorIdx] === ' ') {
          chunk += normalized[cursorIdx];
          cursorIdx += 1;
        }
      }

      const doc = editor.document;
      const lastLine = Math.max(0, doc.lineCount - 1);
      const endPos = doc.lineAt(lastLine).range.end;

      await editor.edit(
        (eb) => {
          eb.insert(endPos, chunk);
        },
        { undoStopBefore: false, undoStopAfter: false }
      );
    } catch (_err) {
      await stopGhostMode(false);
    } finally {
      busyTick = false;
    }
  }, 18);
}

function runCoreEngine(rawText, mode) {
  return new Promise((resolve, reject) => {
    if (!canRunEngine()) {
      reject(new Error('Cong cu da bi vo hieu hoa.'));
      return;
    }
    const engineRoot = installedEngineRoot;
    const pyExe = findPythonExecutable(engineRoot);
    const cliScript = path.join(engineRoot, 'core_engine', 'cli_entry.py');

    const child = spawn(pyExe, [cliScript, '--mode', mode], {
      cwd: engineRoot,
      windowsHide: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' }
    });
    engineProcesses.add(child);

    let stdoutData = '';
    let stderrData = '';

    child.stdout.on('data', (chunk) => {
      stdoutData += chunk.toString('utf8');
    });
    child.stderr.on('data', (chunk) => {
      stderrData += chunk.toString('utf8');
    });
    child.on('error', (err) => {
      engineProcesses.delete(child);
      reject(err);
    });
    child.on('close', () => {
      engineProcesses.delete(child);
      try {
        const parsed = JSON.parse(stdoutData);
        resolve(parsed);
      } catch (e) {
        reject(new Error(stderrData || stdoutData || e.message));
      }
    });

    const payload = JSON.stringify({
      text: rawText,
      mode: mode,
      verify: true
    });
    child.stdin.write(payload, 'utf8');
    child.stdin.end();
  });
}

async function handleEngineCommand(mode) {
  if (!canRunEngine()) {
    return;
  }
  await stopGhostMode(false);
  const editor = await getOrOpenEditor();
  if (!editor || !canRunEngine()) {
    return;
  }

  let { text } = extractTargetText(editor);
  if (!text || !text.trim()) {
    // Neu file dang trong, thu lay tu Clipboard
    const clipText = await vscode.env.clipboard.readText();
    if (!canRunEngine()) {
      return;
    }
    if (clipText && clipText.trim()) {
      text = clipText;
    } else {
      await editor.edit((eb) => {
        eb.insert(
          new vscode.Position(0, 0),
          '# [Thong bao: Hay nhap # yeu cau hoac """ yeu cau """ truoc khi bam Alt+1/2/3/4]\n'
        );
      });
      return;
    }
  }

  const modeNoticeMap = {
    instant: '# [Alt+1: Dang giai nhanh Offline RAG (<0.08s)...]\n',
    full: '# [Alt+2: Dang phan tich AI 3 Tang & chay thu ngam kiem loi...]\n',
    ghost: '# [Alt+3: Dang chuan bi Che do Go Tu Dong (Bam Esc de dung)...]\n',
    self_fix: '# [Alt+4: Dang bat Traceback & tu dong sua loi code...]\n'
  };
  const noticeLine = modeNoticeMap[mode] || '# [Dang xu ly yeu cau...]\n';

  // Hien thi ngay dòng # thong bao de nguoi dung thay phan hoi tuc thi (<0.01s)
  await editor.edit(
    (eb) => {
      eb.insert(new vscode.Position(0, 0), noticeLine);
    },
    { undoStopBefore: false, undoStopAfter: false }
  );

  setStatus('$(loading~spin) Pylance: Indexing...');
  try {
    const res = await runCoreEngine(text, mode);
    if (!canRunEngine()) {
      return;
    }
    const doc = editor.document;
    const lastLine = Math.max(0, doc.lineCount - 1);
    const fullRange = new vscode.Range(
      new vscode.Position(0, 0),
      doc.lineAt(lastLine).range.end
    );

    if (!res || !res.code) {
      await editor.edit((eb) => {
        eb.replace(fullRange, `# [Khong nhan dien duoc yeu cau. Hay viet trong # hoac """ """]\n${text}`);
      });
      setStatus('$(warning) Pylance: Idle', 3000);
      return;
    }

    await vscode.env.clipboard.writeText(res.code);
    if (!canRunEngine()) {
      return;
    }

    if (mode === 'ghost') {
      // Xoa comment cu va bat dau go tu dong tung ky tu tren man hinh
      await editor.edit((eb) => {
        eb.replace(fullRange, '');
      });
      startAutoStreamGhostMode(editor, res.code);
    } else {
      await editor.edit((eb) => {
        eb.replace(fullRange, res.code);
      });
      const badge = res.verified_ok
        ? `$(check) Pylance: Ready (${res.elapsed_sec}s)`
        : '$(warning) Pylance: 1 warning';
      setStatus(badge, 5000);
    }
  } catch (err) {
    if (!canRunEngine()) {
      return;
    }
    await editor.edit((eb) => {
      eb.insert(new vscode.Position(0, 0), `# [Loi Engine: ${err.message}]\n`);
    });
    setStatus('$(warning) Pylance: Offline', 3000);
  }
}

async function handleUninstallAll() {
  if (uninstalling) {
    return;
  }
  uninstalling = true;
  // Khóa đồng bộ trước await đầu tiên, kể cả khi không có editor.
  disableRuntime();
  setStatus('$(loading~spin) Pylance: Uninstalling...');
  try {
    const engineRoot = installedEngineRoot || findEngineRoot();
    const pyExe = findPythonExecutable(engineRoot);
    const candidates = [
      path.join(engineRoot, 'go_cai_dat.py'),
      'D:\\UEH\\ai\\midtermtool\\go_cai_dat.py',
      path.resolve(__dirname, '..', '..', '..', 'go_cai_dat.py')
    ];
    const uninstallScript = candidates.find((script) => fs.existsSync(script));
    if (!uninstallScript) {
      throw new Error('Khong tim thay go_cai_dat.py.');
    }
    await new Promise((resolve, reject) => {
      const child = spawn(pyExe, [uninstallScript], {
        // Không giữ thư mục sắp bị xóa làm cwd trên Windows.
        cwd: os.tmpdir(),
        windowsHide: true,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' }
      });
      let output = '';
      child.stdout.on('data', (chunk) => { output += chunk.toString('utf8'); });
      child.stderr.on('data', (chunk) => { output += chunk.toString('utf8'); });
      child.on('error', reject);
      child.on('close', (code) => {
        if (code === 0) {
          resolve();
        } else {
          reject(new Error(output.trim() || `Trinh go thoat voi ma ${code}`));
        }
      });
    });
    await vscode.env.clipboard.writeText('');
    const editor = vscode.window.activeTextEditor;
    if (editor) {
      await editor.edit((eb) => {
        eb.insert(new vscode.Position(0, 0), '# [Alt+0: DA GO CAI DAT THANH CONG. Reload Window de bo phim tat da nap.]\n');
      });
    }
    setStatus('$(trash) Pylance: Uninstalled');
    const action = await vscode.window.showInformationMessage(
      'Da go cai dat. Reload Window trong cac cua so VS Code/Antigravity dang mo de bo phim tat da nap.',
      'Reload Window'
    );
    if (action === 'Reload Window') {
      await vscode.commands.executeCommand('workbench.action.reloadWindow');
    }
  } catch (err) {
    setStatus('$(warning) Pylance: Uninstall failed');
    await vscode.window.showErrorMessage(`Go cai dat chua hoan tat: ${err.message}`);
  } finally {
    uninstalling = false;
  }
}

function activate(context) {
  runtimeDisabled = false;
  installedEngineRoot = findEngineRoot();
  statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  statusBarItem.text = '$(check) Pylance';
  statusBarItem.tooltip = 'Python Pylance Indentation & Docstring Helper';
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);
  const installWatcher = setInterval(() => canRunEngine(), 250);
  context.subscriptions.push({ dispose: () => clearInterval(installWatcher) });

  context.subscriptions.push(
    vscode.commands.registerCommand('pylanceIndentHelper.instantFormat', () =>
      handleEngineCommand('instant')
    ),
    vscode.commands.registerCommand('pylanceIndentHelper.deepFormat', () =>
      handleEngineCommand('full')
    ),
    vscode.commands.registerCommand('pylanceIndentHelper.ghostMode', () =>
      handleEngineCommand('ghost')
    ),
    vscode.commands.registerCommand('pylanceIndentHelper.silentFix', () =>
      handleEngineCommand('self_fix')
    ),
    vscode.commands.registerCommand('pylanceIndentHelper.uninstallAll', () =>
      handleUninstallAll()
    ),
    vscode.commands.registerCommand('pylanceIndentHelper.cancelGhost', async () => {
      if (isGhostStreaming) {
        await stopGhostMode(true);
      } else {
        vscode.commands.executeCommand('default:cancelSelection');
      }
    })
  );
}

function deactivate() {
  disableRuntime();
}

module.exports = {
  activate,
  deactivate
};
