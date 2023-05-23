from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .dockwidget_ui import DockwidgetUI


class PluginCore:
    def __init__(self, iface):
        self.iface = iface
        self.actions = [] # Not needed for QGIS, just used in the `unload` method.
        self.menu_item = 'Route ADT'

    def initGui(self):
        self.toolbar = self.iface.addToolBar('Route ADT')
        icon = QIcon(':/images/themes/default/mActionOptions.svg')
        self.show_dockwidget_action = QAction(icon, 'Open Dockwidget', self.iface.mainWindow())
        self.show_dockwidget_action.triggered.connect(self.show_dockwidget)
        self.toolbar.addAction(self.show_dockwidget_action)
        self.actions.append(self.show_dockwidget_action)
        self.iface.addPluginToMenu(self.menu_item, self.show_dockwidget_action)

    def show_dockwidget(self):
        self.dw = DockwidgetUI()
        self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.dw)
        self.dw.show()

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.menu_item, action)
            self.toolbar.removeAction(action)

        del self.toolbar
