def classFactory(iface):
    from .core import PluginCore
    return PluginCore(iface)