import { execFile } from "node:child_process";
import * as vscode from "vscode";
import {
  ATTACH_CONFIG_NAME,
  Lang,
  PROJECT_CONFIG_FILE,
  ProjectConfig,
  buildCliArgs,
  buildFallbackAttachConfig,
  parseProjectConfig,
  resolveLang,
  t,
} from "./core";

let taskCounter = 0;

function settings(): vscode.WorkspaceConfiguration {
  return vscode.workspace.getConfiguration("devbridge");
}

function currentLang(): Lang {
  return resolveLang(settings().get<string>("language"), vscode.env.language);
}

async function pickFolder(lang: Lang): Promise<vscode.WorkspaceFolder | undefined> {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) {
    void vscode.window.showErrorMessage(t(lang, "noFolder"));
    return undefined;
  }
  return folders.length === 1 ? folders[0] : vscode.window.showWorkspaceFolderPick();
}

async function readProjectConfig(folder: vscode.WorkspaceFolder): Promise<ProjectConfig> {
  try {
    const bytes = await vscode.workspace.fs.readFile(
      vscode.Uri.joinPath(folder.uri, PROJECT_CONFIG_FILE),
    );
    return parseProjectConfig(Buffer.from(bytes).toString("utf-8"));
  } catch {
    return parseProjectConfig(undefined);
  }
}

/** Resolves with the CLI's version string, or undefined when it cannot be run. */
function cliVersion(cli: string): Promise<string | undefined> {
  return new Promise((resolve) => {
    execFile(cli, ["--version"], { timeout: 15000 }, (error, stdout) => {
      resolve(error ? undefined : stdout.trim());
    });
  });
}

async function ensureCli(lang: Lang): Promise<string | undefined> {
  const cli = settings().get<string>("cliCommand") || "devbridge";
  if ((await cliVersion(cli)) === undefined) {
    void vscode.window.showErrorMessage(t(lang, "cliMissing", { cli }));
    return undefined;
  }
  return cli;
}

/** Runs the CLI as a visible task (no shell, so no quoting problems) and resolves with its exit code. */
function runCli(
  folder: vscode.WorkspaceFolder,
  cli: string,
  args: string[],
  title: string,
): Promise<number | undefined> {
  const name = `${title} #${++taskCounter}`;
  const task = new vscode.Task(
    { type: "devbridge" },
    folder,
    name,
    "devbridge",
    new vscode.ProcessExecution(cli, args, { cwd: folder.uri.fsPath }),
  );
  task.presentationOptions = {
    reveal: vscode.TaskRevealKind.Always,
    panel: vscode.TaskPanelKind.Shared,
    clear: true,
  };
  return new Promise((resolve) => {
    // Subscribe before starting so a fast-finishing process cannot be missed.
    const sub = vscode.tasks.onDidEndTaskProcess((e) => {
      if (e.execution.task.name === name) {
        sub.dispose();
        resolve(e.exitCode);
      }
    });
    vscode.tasks.executeTask(task).then(undefined, () => {
      sub.dispose();
      resolve(undefined);
    });
  });
}

async function attach(folder: vscode.WorkspaceFolder, lang: Lang): Promise<boolean> {
  // Prefer the generated launch.json entry: it carries the path mappings.
  let started = await vscode.debug.startDebugging(folder, ATTACH_CONFIG_NAME);
  if (!started) {
    void vscode.window.showWarningMessage(t(lang, "noLaunchConfig", { name: ATTACH_CONFIG_NAME }));
    const cfg = await readProjectConfig(folder);
    started = await vscode.debug.startDebugging(
      folder,
      buildFallbackAttachConfig(cfg) as vscode.DebugConfiguration,
    );
  }
  if (!started) {
    void vscode.window.showErrorMessage(t(lang, "attachFailed"));
  }
  return started;
}

async function launchAndAttach(): Promise<void> {
  const lang = currentLang();
  const folder = await pickFolder(lang);
  const cli = folder && (await ensureCli(lang));
  if (!folder || !cli) {
    return;
  }
  const timeoutSeconds = settings().get<number>("launchTimeoutSeconds") ?? 60;
  void vscode.window.setStatusBarMessage(t(lang, "launching"), 5000);
  const code = await runCli(
    folder,
    cli,
    buildCliArgs("launch", { lang, projectDir: folder.uri.fsPath, timeoutSeconds }),
    "DevBridge: launch QGIS",
  );
  if (code !== 0) {
    void vscode.window.showErrorMessage(t(lang, "launchFailed", { code: code ?? "?" }));
    return;
  }
  await attach(folder, lang);
}

async function attachOnly(): Promise<void> {
  const lang = currentLang();
  const folder = await pickFolder(lang);
  if (folder) {
    await attach(folder, lang);
  }
}

async function setup(): Promise<void> {
  const lang = currentLang();
  const folder = await pickFolder(lang);
  const cli = folder && (await ensureCli(lang));
  if (!folder || !cli) {
    return;
  }
  const cfg = await readProjectConfig(folder);
  const pluginName = await vscode.window.showInputBox({
    prompt: t(lang, "pluginNamePrompt"),
    value: cfg.pluginName ?? "",
    ignoreFocusOut: true,
  });
  if (pluginName === undefined) {
    return; // cancelled
  }
  void vscode.window.setStatusBarMessage(t(lang, "setupStarted"), 5000);
  await runCli(
    folder,
    cli,
    buildCliArgs("setup", {
      lang,
      projectDir: folder.uri.fsPath,
      port: cfg.port,
      pluginName: pluginName.trim() || undefined,
    }),
    "DevBridge: setup",
  );
}

async function detect(): Promise<void> {
  const lang = currentLang();
  const folder = await pickFolder(lang);
  const cli = folder && (await ensureCli(lang));
  if (folder && cli) {
    await runCli(
      folder,
      cli,
      buildCliArgs("detect", { lang, projectDir: folder.uri.fsPath }),
      "DevBridge: detect QGIS",
    );
  }
}

async function showMenu(): Promise<void> {
  const lang = currentLang();
  const items: Array<vscode.QuickPickItem & { run: () => Promise<void> }> = [
    { label: `$(debug-start) ${t(lang, "menuLaunch")}`, run: launchAndAttach },
    { label: `$(plug) ${t(lang, "menuAttach")}`, run: attachOnly },
    { label: `$(tools) ${t(lang, "menuSetup")}`, run: setup },
    { label: `$(search) ${t(lang, "menuDetect")}`, run: detect },
  ];
  const picked = await vscode.window.showQuickPick(items, { placeHolder: "DevBridge" });
  await picked?.run();
}

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("devbridge.launchAndAttach", launchAndAttach),
    vscode.commands.registerCommand("devbridge.attach", attachOnly),
    vscode.commands.registerCommand("devbridge.setup", setup),
    vscode.commands.registerCommand("devbridge.detect", detect),
    vscode.commands.registerCommand("devbridge.menu", showMenu),
  );

  if (settings().get<boolean>("showStatusBar") ?? true) {
    const item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
    item.text = "$(debug-alt) DevBridge";
    item.tooltip = t(currentLang(), "statusTooltip");
    item.command = "devbridge.menu";
    item.show();
    context.subscriptions.push(item);
  }
}

export function deactivate(): void {}
