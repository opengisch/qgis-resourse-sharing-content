#-*- coding: utf-8 -*-
# version 15.08.2022 with Ivan

"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsProcessingFeatureBasedAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsVertexIterator,
                       QgsPointXY,
                       QgsFeature,
                       QgsLineString)
import numpy as np
from math import sqrt
import itertools
import traceback


class InterpolateMValues(QgsProcessingFeatureBasedAlgorithm):
    """
    Algorithm to interpolate M-values along a line
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return InterpolateMValues()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'interpolatemvalues'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Interpolate M-values along LineStringM')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr('Interpolation LineString values')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'interpolation'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """
        return self.tr("This algorithm interpolates M-values along LineStrings. Input must be of type LineStringM.")

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # We add the input vector features source. It can have any kind of
        # geometry.
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input layer'),
                [QgsProcessing.TypeVectorAnyGeometry]
            )
        )

        # We add a feature sink in which to store our processed features (this
        # usually takes the form of a newly created vector layer when the
        # algorithm is run in QGIS).
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output layer')
            )
        )
    
    def processFeature(self, feature, context, feedback):
        
        try:
            geom = feature.geometry()
            line = geom.constGet()
            vertex_iterator = QgsVertexIterator(line)
            vertex_m = []

            # Iterate over all vertices of the feature and extract M-value
            while vertex_iterator.hasNext():
                vertex = vertex_iterator.next()
                vertex_m.append(vertex.m())

            # Extract length of segments between vertices
            vertices_indices = range(len(vertex_m))
            length_segments = [sqrt(QgsPointXY(line[i]).sqrDist(QgsPointXY(line[j]))) 
                for i,j in itertools.combinations(vertices_indices, 2) 
                if (j - i) == 1]

            # Get all non-zero M-value indices as an array, where interpolations have to start (vertex_start_indices, _si)
            vertex_si = np.nonzero(vertex_m)[0]
            
            m_interpolated = np.copy(vertex_m)

            # Interpolate between all non-zero M-values - take segment lengths between vertices into account
            for i in range(len(vertex_si)-1):
                first_nonzero = vertex_m[vertex_si[i]]
                next_nonzero = vertex_m[vertex_si[i+1]]
                accum_dist = itertools.accumulate(length_segments[vertex_si[i]:vertex_si[i+1]])
                sum_seg = sum(length_segments[vertex_si[i]:vertex_si[i+1]])
                interp_m = [round(((dist/sum_seg)*(next_nonzero-first_nonzero))+first_nonzero,0) for dist in accum_dist]
                m_interpolated[vertex_si[i]:vertex_si[i+1]] = interp_m

            # Copy feature geometry and set interpolated M-values, attribute new geometry to feature
            geom_new = QgsLineString(geom.constGet()) # copy feature geometry
            
            for j in range(len(m_interpolated)):
                geom_new.setMAt(j,m_interpolated[j])
                
            attrs = feature.attributes()
            
            feat_new = QgsFeature()
            feat_new.setAttributes(attrs)
            feat_new.setGeometry(geom_new)

        except Exception:
            s = traceback.format_exc()
            feedback.pushInfo(s)
            self.num_bad += 1
            return []
        
        return [feat_new]