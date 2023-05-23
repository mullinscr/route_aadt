from pathlib import Path

import processing
from qgis.core import QgsProject, QgsGraduatedSymbolRenderer, QgsStyle, QgsVectorLayerSimpleLabeling, QgsPalLayerSettings, QgsTextFormat, edit
from qgis.PyQt.uic import loadUiType
from qgis.PyQt.QtWidgets import QDockWidget
from qgis.PyQt.QtGui import QFont

FORM_CLASS, _ = loadUiType(Path(__file__).parent / 'dockwidget.ui')

class DockwidgetUI(QDockWidget, FORM_CLASS):
    def __init__(self, parent=None):
        super(DockwidgetUI, self).__init__(parent)
        self.setupUi(self)
    
        self.btnViewADTSites.clicked.connect(self.load_adt_sites)
        self.btnRemoveSites.clicked.connect(self.remove_selected_sites)

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
        
        # style layer
        graduated_renderer = QgsGraduatedSymbolRenderer()
        graduated_renderer.setClassAttribute('7 day')
        graduated_renderer.updateClasses(intersecting_adt, QgsGraduatedSymbolRenderer.Jenks, 5)
        color_ramp = QgsStyle().defaultStyle().colorRamp('Spectral')
        graduated_renderer.updateColorRamp(color_ramp)
        graduated_renderer.setSymbolSizes(4,4)
        intersecting_adt.setRenderer(graduated_renderer)

        label_settings  = QgsPalLayerSettings()
        text_format = QgsTextFormat()
        text_format.setFont(QFont("Arial", 10))
        label_settings.setFormat(text_format)
        label_settings.fieldName = "format_number(\"7 day\", 0)"
        label_settings.isExpression = True
        label_settings.dist = 1

        label_settings = QgsVectorLayerSimpleLabeling(label_settings)
        intersecting_adt.setLabelsEnabled(True)
        intersecting_adt.setLabeling(label_settings)

        intersecting_adt.triggerRepaint()

        self.adt_sites = intersecting_adt

        QgsProject.instance().addMapLayer(intersecting_adt)

    def remove_selected_sites(self):
        if not self.adt_sites.getSelectedFeatures():
            return

        with edit(self.adt_sites):
            self.adt_sites.deleteFeatures(
                [f.id() for f in self.adt_sites.getSelectedFeatures()])

    def merge_selected_sites(self):
        ...