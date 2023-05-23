from pathlib import Path

import processing
from qgis.core import QgsProject, QgsGraduatedSymbolRenderer, QgsStyle, QgsVectorLayerSimpleLabeling, QgsPalLayerSettings, QgsTextFormat, edit, QgsGeometry
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
        self.btnMergeSites.clicked.connect(self.merge_selected_sites)
        self.btnGenerateResult.clicked.connect(self.generate_result)

    def load_adt_sites(self):
        self.route_lyr = self.cmbxRouteLyr.currentLayer()
        self.adt_lyr =  self.cmbxADTLyr.currentLayer()
        self.buff_dist = self.spbxBufferM.value()

        buffered = processing.run("native:buffer",
            {'INPUT':self.route_lyr,
            'DISTANCE':self.buff_dist,
            'SEGMENTS':120,
            'END_CAP_STYLE':0,
            'JOIN_STYLE':0,
            'MITER_LIMIT':2,
            'DISSOLVE':False,
            'OUTPUT':'memory:'}
            )['OUTPUT']

        intersecting_adt = processing.run("native:extractbylocation",
            {'INPUT':self.adt_lyr,
            'PREDICATE':[0],
            'INTERSECT':buffered,
            'OUTPUT':'memory:'})['OUTPUT']

        intersecting_adt.setName(f'ADT sites ({self.buff_dist} m buffer): {self.route_lyr.sourceName()}')
        
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
        if not self.adt_sites.getSelectedFeatures():
            return
        
        # sum their 7 day count
        total_count = 0
        for feat in self.adt_sites.getSelectedFeatures():
            total_count += feat['7 day']
        
        # update each feature with this value
        with edit(self.adt_sites):
            for feat in self.adt_sites.getSelectedFeatures():
                feat['7 day'] = total_count
                self.adt_sites.updateFeature(feat)
    
    def generate_result(self):
        # create a total route geometry
        vertices = []
        feats = []
        for feat in self.route_lyr.getFeatures():
           feats.append(feat)
        feats = sorted(feats, key=lambda x: x['fid']) # expects route builder output
        
        for feat in feats:
            vertices.extend([v for v in feat.geometry().vertices()])
        route_geom = QgsGeometry.fromPolyline(vertices)

        route_length = route_geom.length() * 2 # times 2 as drawn single dir
        distances = []
        adts = [] 
        throughput = 0

        for site in self.adt_sites.getFeatures():
            geom = site.geometry()
            # transform to 27700
            adt = site['7 day']
            dist = route_geom.lineLocatePoint(geom)
            distances.append(dist)
            adts.append(adt)

        r = zip(distances, adts)
        r = sorted(r, key=lambda x: x[0])

        import numpy as np
        print(np.mean(adts), np.median(adts))

        for n in range(1, len(r) - 1):
            d_ahead = (r[n + 1][0] + r[n][0]) / 2
            d_behind = (r[n][0] + r[n - 1][0]) / 2
            d = d_ahead - d_behind
            throughput += (d * 2 * r[n][1]) # * 2 as routes are drawn single dir

        # first site
        d = (r[1][0] + r[0][0]) / 2
        throughput += (d * 2 * r[0][1])

        # last site
        d = route_geom.length() - ((r[-1][0] + r[-2][0]) / 2)
        throughput += (d * 2 * r[-1][1])

        print(f'THROUGHPUT (km): {(throughput / 1000):,.0f}\nADT: {(throughput / route_length):,.0f}')