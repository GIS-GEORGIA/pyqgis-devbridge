"""Generates PyCharm's "Python Debug Server" run configuration
(``.idea/runConfigurations/*.xml``) - the one remaining fully-manual
PyCharm step. The QGIS side (detecting the installed PyCharm build,
installing the matching ``pydevd-pycharm``, connecting) is already
automated by ``qgis_plugin/pycharm_bridge.py``; ``pycharm_config.py``
covers the rest of what a user still has to do by hand.

The exact XML shape (``type="PyRemoteDebugConfigurationType"``,
``factoryName="Python Remote Debug"``, the ``PORT``/``HOST``/
``REDIRECT_OUTPUT``/``SUSPEND_AFTER_CONNECT`` options, ``PathMappingSettings``)
is not guessed from memory - it is cross-checked against:

- the field labels PyCharm 2025.2.6.1 itself ships, extracted directly
  from its own ``python-ce.jar`` (``messages/PyBundle.properties``):
  ``run.configuration.remote.debug.visible.name=Python Debug Server``,
  ``run.configuration.remote.debug.name=Python Remote Debug``, plus the
  "Port:" / "IDE host name:" / "Redirect output to console" / "Suspend
  after connect" field labels this module's options map to;
- `QuantConnect/lean-cli <https://github.com/QuantConnect/lean-cli>`_'s
  ``project_manager.py``, a real, actively used open-source tool
  generating this exact configuration for the same
  ``pydevd_pycharm.settrace()`` workflow;
- opening a real PyCharm 2025.2.6.1 project containing a file built by
  this module produces no error/warning in its own ``idea.log``
  (``RunManager`` loads it silently, the file is indexed as a normal
  project file).

**Not confirmed**: actually pressing Debug on the generated configuration
in a real PyCharm window - no UI automation is available in this
environment, the same caveat already carried by the VS Code extension's
attach flow elsewhere in this project. If it turns out to need a tweak,
only this module and its tests are affected.
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import quoteattr

RUN_CONFIG_NAME = "PyQGIS Debug Server"


def build_run_config_xml(name: str = RUN_CONFIG_NAME, host: str = "localhost", port: int = 12345,
                         local_root: str = "$PROJECT_DIR$", remote_root: str | None = None) -> str:
    mapping = ""
    path_mappings = ""
    if remote_root:
        mapping = f'\n          <mapping local-root={quoteattr(local_root)} remote-root={quoteattr(remote_root)} />'
        path_mappings = f'''
    <PathMappingSettings>
      <option name="pathMappings">
        <list>{mapping}
        </list>
      </option>
    </PathMappingSettings>'''
    return f'''<component name="ProjectRunConfigurationManager">
  <configuration default="false" name={quoteattr(name)} type="PyRemoteDebugConfigurationType" factoryName="Python Remote Debug">
    <option name="PORT" value="{port}" />
    <option name="HOST" value={quoteattr(host)} />{path_mappings}
    <option name="REDIRECT_OUTPUT" value="true" />
    <option name="SUSPEND_AFTER_CONNECT" value="false" />
    <method v="2" />
  </configuration>
</component>
'''


def _config_filename(name: str) -> str:
    """PyCharm itself names shared-run-configuration files after the
    configuration, with anything not alphanumeric turned into `_`."""
    return "".join(c if c.isalnum() else "_" for c in name) + ".xml"


def write_run_config(project_dir: Path, name: str = RUN_CONFIG_NAME, host: str = "localhost",
                     port: int = 12345, local_root: str = "$PROJECT_DIR$",
                     remote_root: str | None = None) -> Path:
    """Always (re)writes the file - this is a dedicated file devbridge
    itself owns, not a shared one to merge into, so a later `devbridge
    setup` refreshing host/port here is expected, the same tradeoff
    already accepted for `.devbridge.json`."""
    run_configs_dir = Path(project_dir) / ".idea" / "runConfigurations"
    run_configs_dir.mkdir(parents=True, exist_ok=True)
    path = run_configs_dir / _config_filename(name)
    path.write_text(
        build_run_config_xml(name=name, host=host, port=port, local_root=local_root, remote_root=remote_root),
        encoding="utf-8",
    )
    return path
