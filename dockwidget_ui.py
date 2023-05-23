from pathlib import Path

from qgis.PyQt.uic import loadUiType
from qgis.PyQt.QtWidgets import QDockWidget

FORM_CLASS, _ = loadUiType(Path(__file__).parent / 'dockwidget.ui')

class DockwidgetUI(QDockWidget, FORM_CLASS):
    def __init__(self, parent=None):
        super(DockwidgetUI, self).__init__(parent)
        self.setupUi(self)