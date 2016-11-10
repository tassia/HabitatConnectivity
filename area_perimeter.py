#!/usr/bin/python

# Computes area and perimeter as new attributes for all features.
# Created to debug anomalies with area and perimeter computed values.
# We finally figured out that it was an issue with units (feet/meter) and the
# workaround was to divide the computed value by a factor of 3.28 per dimension
# of the computed value.

import os
from PyQt4.QtCore import QVariant
from qgis.utils import iface
from qgis.core import *

# paths for input folder and output shapefile
PATH = "/media/tassia/rouge/ENVR401/Sandbox/Clipped_Parcel_1.shp"

layer = iface.addVectorLayer(PATH, "Layer", "ogr")

layer.startEditing()
layer.dataProvider().addAttributes([QgsField('P', QVariant.Double),
                                          QgsField('A', QVariant.Double)])
layer.updateFields()                                          

for feature in layer.getFeatures():
    print feature.geometry().area
    feature['A'] = feature.geometry().area()/(3.28*3.28)
    feature['P'] = feature.geometry().length()/3.28
    layer.updateFeature(feature)

# Save all changes to 
layer.commitChanges()

print 'completed'
