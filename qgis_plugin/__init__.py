"""QGIS plugin entry point (required `classFactory` hook)."""


def classFactory(iface):  # noqa: N802 - QGIS API requires this exact name
    from .plugin import DevBridgePlugin
    return DevBridgePlugin(iface)
