# -*- coding: utf-8 -*-

import requests
import json

from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsGeometry, QgsPointXY, QgsWkbTypes,
    QgsFeature, QgsField, QgsFields,
    QgsCoordinateReferenceSystem,
    QgsProcessingAlgorithm,
    QgsProcessing,
    QgsFeatureSink,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterField, QgsProcessingFeatureSource,
    QgsProcessingParameterVectorLayer
)


class SwissPublicTransportGetLocationFromName(QgsProcessingAlgorithm):

    INPUT_LOCATIONS = 'INPUT_LOCATIONS'
    INPUT_FIELD_NAME = 'INPUT_FIELD_NAME'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return SwissPublicTransportGetLocationFromName()

    def group(self):
        return self.tr('Swiss Public Transport API')

    def groupId(self):
        return 'SwissPublicTransportAPI'

    def __init__(self):
        super().__init__()

    def initAlgorithm(self, config):

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_LOCATIONS,
                self.tr("Input locations"),
                [QgsProcessing.TypeVector]
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.INPUT_FIELD_NAME,
                self.tr('Search query field'),
                parentLayerParameterName=self.INPUT_LOCATIONS,
                type=QgsProcessingParameterField.String
            )
        )

        # Define output parameters
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "OUTPUT", self.tr("Swiss Public Transport Locations"), type=QgsProcessing.TypeVectorPoint
            )
        )

    def name(self):
        return 'spt-getlocationfromname'

    def displayName(self):
        return self.tr('Get Location from name')

    def outputWkbType(self, input_wkb_type):
        return QgsWkbTypes.Point

    def prepareAlgorithm(self, parameters, context, feedback):
        self.headers = {'User-Agent': 'qgis/opengis.ch'}
        return True

    def sourceFlags(self):
        return QgsProcessingFeatureSource.FlagSkipGeometryValidityChecks

    def processAlgorithm(self, parameters, context, feedback):

        input_locations_data = self.parameterAsLayer(
            parameters, self.INPUT_LOCATIONS, context
        )
        field_input_name = self.parameterAsString(
            parameters, self.INPUT_FIELD_NAME, context
        )

        output_fields = QgsFields(input_locations_data.fields())
        output_fields.append(QgsField('stp_id', QVariant.Int, "int"))
        output_fields.append(QgsField('stp_name', QVariant.String, "text"))
        output_fields.append(QgsField('stp_x', QVariant.Double, "double"))
        output_fields.append(QgsField('stp_y', QVariant.Double, "double"))

        (sink, sink_id) = self.parameterAsSink(
            parameters, "OUTPUT", context, output_fields,
            QgsWkbTypes.Point, QgsCoordinateReferenceSystem("EPSG:4326")
        )

        for feature in input_locations_data.getFeatures():

            payload = {
                'query': feature[field_input_name], 'type': 'station'}
            url = 'http://transport.opendata.ch/v1/locations'
            resp = requests.get(url, params=payload, headers=self.headers)
            data = json.loads(resp.content)

            new_feature = QgsFeature(output_fields)

            # Clone the existing attributes
            for i in range(len(input_locations_data.fields())):
                new_feature.setAttribute(i, feature.attribute(i))

            if len(data['stations']) == 0:
                pass
            else:
                new_feature['stp_id'] = data['stations'][0]['id']
                # x/y are switched
                new_feature['stp_x'] = data['stations'][0]['coordinate']['y']
                new_feature['stp_y'] = data['stations'][0]['coordinate']['x']
                new_feature['stp_name'] = data['stations'][0]['name']

            if not data['stations'][0]['coordinate']['x'] or not data['stations'][0]['coordinate']['y']:
                new_feature.setGeometry(QgsGeometry())
            else:
                # x/y are switched
                new_feature.setGeometry(
                    QgsGeometry.fromPointXY(
                        QgsPointXY(
                            data['stations'][0]['coordinate']['y'],
                            data['stations'][0]['coordinate']['x']
                        )
                    )
                )

            sink.addFeature(new_feature, QgsFeatureSink.FastInsert)

        return {"OUTPUT": sink_id}
