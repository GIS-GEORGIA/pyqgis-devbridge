import assert from "node:assert/strict";
import { test } from "node:test";
import {
  ATTACH_CONFIG_NAME,
  STRINGS,
  buildCliArgs,
  buildFallbackAttachConfig,
  parseProjectConfig,
  resolveLang,
  t,
} from "../src/core";

test("en and ka string tables have identical keys", () => {
  assert.deepEqual(Object.keys(STRINGS.en).sort(), Object.keys(STRINGS.ka).sort());
});

test("resolveLang honours the setting, else follows the display language", () => {
  assert.equal(resolveLang("ka", "en-US"), "ka");
  assert.equal(resolveLang("en", "ka"), "en");
  assert.equal(resolveLang("auto", "ka"), "ka");
  assert.equal(resolveLang(undefined, "de"), "en");
});

test("t substitutes variables and falls back to the key", () => {
  assert.match(t("en", "cliMissing", { cli: "devbridge" }), /'devbridge'/);
  assert.equal(t("ka", "nope"), "nope");
  assert.match(t("en", "launchFailed"), /\{code\}/); // unknown vars stay visible
});

test("parseProjectConfig mirrors the Python reader's fallbacks", () => {
  assert.equal(parseProjectConfig(undefined).port, 5678);
  assert.equal(parseProjectConfig("not json").host, "localhost");
  const ok = parseProjectConfig('{"host":"h","port":6001,"pluginName":"p","venvName":".v"}');
  assert.deepEqual(ok, { host: "h", port: 6001, pluginName: "p", venvName: ".v" });
  const bad = parseProjectConfig('{"host":"","port":"abc","pluginName":7}');
  assert.deepEqual(bad, { host: "localhost", port: 5678, pluginName: null, venvName: ".venv" });
  assert.equal(parseProjectConfig('{"port":70000}').port, 5678);
  assert.equal(parseProjectConfig("[1,2]").port, 5678);
});

test("buildCliArgs puts --lang before the subcommand", () => {
  assert.deepEqual(buildCliArgs("launch", { lang: "ka", projectDir: "/p", timeoutSeconds: 30 }), [
    "--lang", "ka", "launch", "--wait-ready", "--project-dir", "/p", "--timeout", "30",
  ]);
  assert.deepEqual(buildCliArgs("setup", { projectDir: "/p", port: 5700, pluginName: "demo" }), [
    "setup", "--project-dir", "/p", "--port", "5700", "--plugin-name", "demo",
  ]);
  assert.deepEqual(buildCliArgs("detect", { lang: "en", projectDir: "/p" }), ["--lang", "en", "detect"]);
});

test("fallback attach config uses the project host/port and the shared name", () => {
  const cfg = buildFallbackAttachConfig({ host: "h", port: 1, pluginName: null, venvName: ".venv" });
  assert.equal(cfg.name, ATTACH_CONFIG_NAME);
  assert.deepEqual(cfg.connect, { host: "h", port: 1 });
});
