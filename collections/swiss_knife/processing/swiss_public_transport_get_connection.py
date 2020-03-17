# -*- coding: utf-8 -*-

import requests
import json

from PyQt5.QtCore import QCoreApplication, QVariant, QDateTime
from qgis.core import (
    QgsVectorLayer,
    QgsFeature, QgsField, QgsFields,
    QgsCoordinateReferenceSystem,
    QgsProcessingAlgorithm,
    QgsProcessing,
    QgsFeatureSink,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterEnum,
    QgsProcessingParameterDateTime,
    QgsProcessingParameterField,
    QgsProcessingFeatureSource,
    QgsProcessingParameterVectorLayer
)


class SwissPublicTransportGetConnection(QgsProcessingAlgorithm):

    INPUT_LAYER = 'INPUT_LAYER'
    FROM_FIELD = 'FROM_FIELD'
    TO_FIELD = 'TO_FIELD'
    METHOD = 'METHOD'
    DATE_TIME = 'DATE_TIME'

    SOONEST = 'SOONEST'
    FASTEST = 'FASTEST'
    METHODS = [SOONEST, FASTEST]

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return SwissPublicTransportGetConnection()

    def group(self):
        return self.tr('Swiss Public Transport API')

    def groupId(self):
        return 'SwissPublicTransportAPI'

    def __init__(self):
        super().__init__()

    def initAlgorithm(self, config):

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_LAYER,
                self.tr("Input layer"),
                [QgsProcessing.TypeVector]
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.FROM_FIELD,
                self.tr('From'),
                parentLayerParameterName=self.INPUT_LAYER,
                type=QgsProcessingParameterField.String
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.TO_FIELD,
                self.tr('To'),
                parentLayerParameterName=self.INPUT_LAYER,
                type=QgsProcessingParameterField.String
            )
        )

        self.addParameter(
            QgsProcessingParameterDateTime(
                self.DATE_TIME,
                self.tr('Departing time'),
                type=QgsProcessingParameterDateTime.Type.DateTime,
                defaultValue=QDateTime.currentDateTime()
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.METHOD, self.tr("Returned result"), options=self.METHODS, defaultValue=0
            )
        )

        # Define output parameters
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "OUTPUT", self.tr("Swiss Public Transport Connections"), type=QgsProcessing.TypeVector
            )
        )

    def name(self):
        return 'spt-getconnection'

    def displayName(self):
        return self.tr('Get Connection')

    def prepareAlgorithm(self, parameters, context, feedback):
        self.headers = {'User-Agent': 'qgis/opengis.ch'}
        return True

    def sourceFlags(self):
        return QgsProcessingFeatureSource.FlagSkipGeometryValidityChecks

    def processAlgorithm(self, parameters, context, feedback):

        input_layer: QgsVectorLayer = self.parameterAsLayer(parameters, self.INPUT_LAYER, context)
        from_field = self.parameterAsString(parameters, self.FROM_FIELD, context)
        to_field = self.parameterAsString(parameters, self.TO_FIELD, context)
        date_time: QDateTime = self.parameterAsDateTime(parameters, self.DATE_TIME, context)
        method = self.METHODS[self.parameterAsEnum(parameters, self.METHOD, context)]

        output_fields = QgsFields(input_layer.fields())
        output_fields.append(QgsField('spt_duration', QVariant.Double, "double"))

        (sink, sink_id) = self.parameterAsSink(
            parameters, "OUTPUT", context, output_fields,
            input_layer.wkbType(), input_layer.crs()
        )

        feature_count = input_layer.featureCount()
        progress = 0

        for feature in input_layer.getFeatures():
            feedback.setProgress(progress/feature_count*100)
            progress += 1

            payload = {
                'from': feature[from_field],
                'to': feature[to_field],
                'date': date_time.date().toString('yyyy-MM-dd'),
                'time': date_time.time().toString('HH:mm')
            }
            url = 'http://transport.opendata.ch/v1/connections'
            resp = requests.get(url, params=payload, headers=self.headers)
            connections = json.loads(resp.content)['connections']

            new_feature = QgsFeature(output_fields)
            new_feature.setGeometry(feature.geometry())

            # Clone the existing attributes
            for i in range(len(input_layer.fields())):
                new_feature.setAttribute(i, feature.attribute(i))

            if len(connections) == 0:
                pass
            else:
                index = 0
                duration = 9999999
                if method == self.SOONEST:
                    index = 0
                    duration = (connections[0]['to']['arrivalTimestamp']-connections[0]['from']['departureTimestamp'])/60  # in minutes
                else:
                    for i in range(len(connections)):
                        new_duration = (connections[i]['to']['arrivalTimestamp']-connections[i]['from']['departureTimestamp'])/60  # in minutes
                        if new_duration < duration:
                            duration = new_duration
                            index = i
                new_feature['spt_duration'] = duration

            sink.addFeature(new_feature, QgsFeatureSink.FastInsert)

        return {"OUTPUT": sink_id}
