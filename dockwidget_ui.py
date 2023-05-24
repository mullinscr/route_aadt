from pathlib import Path

import numpy as np

import processing
from qgis.core import QgsProject, QgsGraduatedSymbolRenderer, QgsStyle, QgsVectorLayerSimpleLabeling, QgsPalLayerSettings, QgsTextFormat, edit, QgsGeometry, QgsFeature, QgsVectorLayer, QgsPoint, QgsField
from qgis.PyQt.uic import loadUiType
from qgis.PyQt.QtWidgets import QDockWidget
from qgis.PyQt.QtCore import QVariant
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

    def _style_layer(self, layer, size=4):
        graduated_renderer = QgsGraduatedSymbolRenderer()
        graduated_renderer.setClassAttribute('aadt')
        graduated_renderer.updateClasses(layer, QgsGraduatedSymbolRenderer.Jenks, 5)
        color_ramp = QgsStyle().defaultStyle().colorRamp('Spectral')
        graduated_renderer.updateColorRamp(color_ramp)
        graduated_renderer.setSymbolSizes(size, size)
        layer.setRenderer(graduated_renderer)

        label_settings  = QgsPalLayerSettings()
        text_format = QgsTextFormat()
        text_format.setFont(QFont("Arial", 10))
        label_settings.setFormat(text_format)
        label_settings.fieldName = "format_number(\"aadt\", 0)"
        label_settings.isExpression = True
        label_settings.dist = 1
        label_settings = QgsVectorLayerSimpleLabeling(label_settings)
        layer.setLabelsEnabled(True)
        layer.setLabeling(label_settings)

        layer.triggerRepaint()

        #' TODO if feature count < classes then only do that number of classes

        return layer

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
        self.adt_sites = self._style_layer(intersecting_adt)

        QgsProject.instance().addMapLayer(intersecting_adt)

    def remove_selected_sites(self):
        if not self.adt_sites.getSelectedFeatures():
            return

        with edit(self.adt_sites):
            self.adt_sites.deleteFeatures(
                [f.id() for f in self.adt_sites.getSelectedFeatures()])

        self._style_layer(self.adt_sites)

    def merge_selected_sites(self):
        if not self.adt_sites.getSelectedFeatures():
            return
        
        # sum their 7 day count
        total_count = 0
        for feat in self.adt_sites.getSelectedFeatures():
            total_count += feat['aadt']
        
        # update each feature with this value
        with edit(self.adt_sites):
            for feat in self.adt_sites.getSelectedFeatures():
                feat['aadt'] = total_count
                self.adt_sites.updateFeature(feat)
    
        self._style_layer(self.adt_sites)

    def create_adt_route_layer(self, route_geom, data):
        # take the route geom,
        # split into separate geometries as per the distances
        # provide each one a 7 day adt value as per adts
        route_vertices = list(route_geom.vertices())
        start_v = 0
        
        part_feats = []
        previous_pt = None
        
        for dist, adt in data:
            interpolated_point = route_geom.interpolate(dist).asPoint()
            _, closest_seg_pt, v_after, _ = route_geom.closestSegmentWithContext(interpolated_point)
            # collect the vertexes of the route_geom
            if v_after == -1:
                v_after = len(route_vertices) - 1
            part_geom = QgsGeometry.fromPolyline(route_vertices[start_v: v_after - 1] + [QgsPoint(closest_seg_pt.x(), closest_seg_pt.y())])
            if previous_pt:
                part_geom.insertVertex(previous_pt.x(), previous_pt.y(), 0)
            feat = QgsFeature()
            feat.setGeometry(part_geom)
            feat.setAttributes([adt])
            part_feats.append(feat)
            start_v = v_after
            previous_pt = closest_seg_pt

        # create lyr and add these feats to it
        uri = "linestring?crs=epsg:27700"
        mem_layer = QgsVectorLayer(uri, f'Route ADT: {self.route_lyr.sourceName()}', "memory")
        mem_layer_dp = mem_layer.dataProvider()
        mem_layer_dp.addAttributes([QgsField("aadt", QVariant.Int)])
        mem_layer.updateFields()
        mem_layer_dp.addFeatures(part_feats)
        route_adt = self._style_layer(mem_layer, size=1)

        QgsProject.instance().addMapLayer(route_adt)

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
        feat_pts = []
        interp_dists = []
        throughput = 0

        for site in self.adt_sites.getFeatures():
            geom = site.geometry()
            # TODO transform to 27700 # not needed currently
            adt = site['aadt']
            dist = route_geom.lineLocatePoint(geom)
            distances.append(dist)
            adts.append(adt)
            feat_pts.append(geom.asPoint())

        r = zip(distances, adts, feat_pts)
        r = sorted(r, key=lambda x: x[0])

        # first site
        d = (r[1][0] + r[0][0]) / 2
        throughput += (d * 2 * r[0][1])
        interp_dists.append((d, r[0][1]))

        for n in range(1, len(r) - 1):
            d_ahead = (r[n + 1][0] + r[n][0]) / 2
            d_behind = (r[n][0] + r[n - 1][0]) / 2
            d = d_ahead - d_behind
            interp_dists.append((d_ahead, r[n][1]))
            throughput += (d * 2 * r[n][1]) # * 2 as routes are drawn single dir

        # last site
        d = route_geom.length() - ((r[-1][0] + r[-2][0]) / 2)
        throughput += (d * 2 * r[-1][1])
        interp_dists.append((route_geom.length(), r[-1][1]))

        self.txtResults.setPlainText(f'THROUGHPUT (km): {(throughput / 1000):,.0f}\nSpot ADT: {(throughput / route_length):,.0f}')

        self.create_adt_route_layer(route_geom, interp_dists)
