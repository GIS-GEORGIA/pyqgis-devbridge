// Pure logic (no `vscode` import) so it can be unit-tested with plain Node.

export type Lang = "en" | "ka";

export const ATTACH_CONFIG_NAME = "PyQGIS: Attach to running QGIS";
export const PROJECT_CONFIG_FILE = ".devbridge.json";

/**
 * The extension keeps its own tiny string table instead of relying on VS Code's
 * display-language machinery: the user can pick the language independently
 * (setting `devbridge.language`), and it works even when VS Code itself has no
 * Georgian display language installed.
 */
export const STRINGS: Record<Lang, Record<string, string>> = {
  en: {
    noFolder: "DevBridge: open a folder first.",
    cliMissing:
      "DevBridge: the '{cli}' command was not found. Install the CLI (pip install -e . in the pyqgis-devbridge repo) or set 'devbridge.cliCommand'.",
    launching: "DevBridge: starting QGIS with the debug bridge...",
    launchFailed:
      "DevBridge: QGIS did not start the debug bridge (exit code {code}). See the DevBridge terminal for details.",
    attachFailed:
      "DevBridge: could not start the debug session. Is the 'Python Debugger' extension (ms-python.debugpy) installed?",
    noLaunchConfig:
      "DevBridge: launch.json has no \"{name}\" entry; attaching with defaults and no path mappings. Run 'DevBridge: Set up PyQGIS environment' to generate it.",
    pluginNamePrompt:
      "Folder name QGIS loads your plugin from (optional; enables breakpoint path mapping)",
    setupStarted: "DevBridge: setup started, see the terminal panel.",
    menuLaunch: "Launch QGIS with debugger and attach",
    menuAttach: "Attach to running QGIS",
    menuSetup: "Set up PyQGIS environment for this folder",
    menuDetect: "Detect QGIS installation",
    statusTooltip: "DevBridge: PyQGIS debugging actions",
  },
  ka: {
    noFolder: "DevBridge: ჯერ გახსენით საქაღალდე.",
    cliMissing:
      "DevBridge: ბრძანება '{cli}' ვერ მოიძებნა. დააინსტალირეთ CLI (pip install -e . pyqgis-devbridge repo-ში) ან შეცვალეთ 'devbridge.cliCommand'.",
    launching: "DevBridge: QGIS-ის გაშვება დებაგ ხიდით...",
    launchFailed:
      "DevBridge: QGIS-მა დებაგ ხიდი ვერ გაუშვა (გამოსვლის კოდი {code}). დეტალებისთვის იხილეთ DevBridge ტერმინალი.",
    attachFailed:
      "DevBridge: დებაგ სესიის დაწყება ვერ მოხერხდა. დაინსტალირებულია თუ არა 'Python Debugger' extension (ms-python.debugpy)?",
    noLaunchConfig:
      "DevBridge: launch.json-ში ჩანაწერი \"{name}\" არ არის; ვუკავშირდები ნაგულისხმევი პარამეტრებით, path mapping-ის გარეშე. გაუშვით 'DevBridge: PyQGIS გარემოს მომზადება' მის შესაქმნელად.",
    pluginNamePrompt:
      "საქაღალდის სახელი, საიდანაც QGIS თქვენს plugin-ს ტვირთავს (არასავალდებულო; ჩართავს breakpoint-ების path mapping-ს)",
    setupStarted: "DevBridge: მომზადება დაიწყო, იხილეთ ტერმინალის პანელი.",
    menuLaunch: "QGIS-ის გაშვება დებაგერით და დაკავშირება",
    menuAttach: "გაშვებულ QGIS-თან დაკავშირება",
    menuSetup: "PyQGIS გარემოს მომზადება ამ საქაღალდისთვის",
    menuDetect: "QGIS ინსტალაციის მოძიება",
    statusTooltip: "DevBridge: PyQGIS დებაგინგის მოქმედებები",
  },
};

export function resolveLang(setting: string | undefined, vscodeLanguage: string): Lang {
  if (setting === "en" || setting === "ka") {
    return setting;
  }
  return vscodeLanguage.toLowerCase().startsWith("ka") ? "ka" : "en";
}

export function t(lang: Lang, key: string, vars: Record<string, string | number> = {}): string {
  const template = STRINGS[lang][key] ?? STRINGS.en[key] ?? key;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in vars ? String(vars[name]) : whole,
  );
}

export interface ProjectConfig {
  host: string;
  port: number;
  pluginName: string | null;
  venvName: string;
}

export const DEFAULT_PROJECT_CONFIG: ProjectConfig = {
  host: "localhost",
  port: 5678,
  pluginName: null,
  venvName: ".venv",
};

/** Mirrors devbridge.project_config.read_project_config: never throws. */
export function parseProjectConfig(text: string | undefined): ProjectConfig {
  const config: ProjectConfig = { ...DEFAULT_PROJECT_CONFIG };
  if (!text) {
    return config;
  }
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    return config;
  }
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    return config;
  }
  const d = data as Record<string, unknown>;
  if (typeof d.host === "string" && d.host.trim()) {
    config.host = d.host.trim();
  }
  if (typeof d.port === "number" && Number.isInteger(d.port) && d.port >= 1 && d.port <= 65535) {
    config.port = d.port;
  }
  if (typeof d.pluginName === "string" && d.pluginName.trim()) {
    config.pluginName = d.pluginName.trim();
  }
  if (typeof d.venvName === "string" && d.venvName.trim()) {
    config.venvName = d.venvName.trim();
  }
  return config;
}

export interface CliOptions {
  lang?: Lang;
  projectDir: string;
  timeoutSeconds?: number;
  port?: number;
  pluginName?: string;
}

/** The `--lang` flag belongs to the top-level parser, so it goes before the subcommand. */
export function buildCliArgs(kind: "launch" | "setup" | "detect", o: CliOptions): string[] {
  const args: string[] = [];
  if (o.lang) {
    args.push("--lang", o.lang);
  }
  args.push(kind);
  if (kind === "launch") {
    args.push("--wait-ready", "--project-dir", o.projectDir);
    if (o.timeoutSeconds !== undefined) {
      args.push("--timeout", String(o.timeoutSeconds));
    }
  } else if (kind === "setup") {
    args.push("--project-dir", o.projectDir);
    if (o.port !== undefined) {
      args.push("--port", String(o.port));
    }
    if (o.pluginName) {
      args.push("--plugin-name", o.pluginName);
    }
  }
  return args;
}

/** Used only when launch.json lacks the generated entry. */
export function buildFallbackAttachConfig(cfg: ProjectConfig): Record<string, unknown> {
  return {
    name: ATTACH_CONFIG_NAME,
    type: "debugpy",
    request: "attach",
    connect: { host: cfg.host, port: cfg.port },
    justMyCode: false,
  };
}
