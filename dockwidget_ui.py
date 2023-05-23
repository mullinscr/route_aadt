from pathlib import Path

import processing
from qgis.core import QgsProject
from qgis.PyQt.uic import loadUiType
from qgis.PyQt.QtWidgets import QDockWidget

FORM_CLASS, _ = loadUiType(Path(__file__).parent / 'dockwidget.ui')

class DockwidgetUI(QDockWidget, FORM_CLASS):
    def __init__(self, parent=None):
        super(DockwidgetUI, self).__init__(parent)
        self.setupUi(self)
    
        self.btnViewADTSites.clicked.connect(self.load_adt_sites)

    def load_adt_sites(self):
        route_lyr = self.cmbxRouteLyr.currentLayer()
        adt_lyr =  self.cmbxADTLyr.currentLayer()
        buff_dist = self.spbxBufferM.value()

        buffered = processing.run("native:buffer",
            {'INPUT':route_lyr,
            'DISTANCE':buff_dist,
            'SEGMENTS':120,
            'END_CAP_STYLE':0,
            'JOIN_STYLE':0,
            'MITER_LIMIT':2,
            'DISSOLVE':False,
            'OUTPUT':'memory:'}
            )['OUTPUT']

        intersecting_adt = processing.run("native:extractbylocation",
            {'INPUT':adt_lyr,
            'PREDICATE':[0],
            'INTERSECT':buffered,
            'OUTPUT':'memory:'})['OUTPUT']

        intersecting_adt.setName(f'ADT sites ({buff_dist} m buffer): {route_lyr.sourceName()}')
        # TODO add QML styling from file
        QgsProject.instance().addMapLayer(intersecting_adt)
        # TODO "select" this layer in the layer tree


    def remove_selected_sites(self):
        ...

    def merge_selected_sites(self):
        ...