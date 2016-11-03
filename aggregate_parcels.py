import os
from PyQt4.QtCore import QVariant
from qgis.utils import iface
from qgis.core import *

# paths for input folder and output shapefile
PARCELS_PATH = "/media/tassia/rouge/ENVR401/Richford-GIS/Clipped_Parcels"
MERGED_PARCELS_PATH = os.path.join(PARCELS_PATH,"Merged_Parcels.shp")

# feature fields for parcel patches to be merged
_LULC_FIELD = 'LULC'
_AREA_FIELD = 'Area'
_PERIMETER_FIELD = 'Perimeter'
_PARCEL_FIELD = 'Parcel_ID'
_PATCH_FIELD = 'Patch_ID'

fields = QgsFields()
fields.append(QgsField(_LULC_FIELD, QVariant.Int))
fields.append(QgsField(_AREA_FIELD, QVariant.Double))
fields.append(QgsField(_PERIMETER_FIELD, QVariant.Double))
fields.append(QgsField(_PARCEL_FIELD, QVariant.Int))
fields.append(QgsField(_PATCH_FIELD, QVariant.Int))

merged_parcels_writer = QgsVectorFileWriter(MERGED_PARCELS_PATH, "CP1250", fields, QGis.WKBPolygon, QgsCoordinateReferenceSystem(102745, QgsCoordinateReferenceSystem.EpsgCrsId), "ESRI Shapefile")

if merged_parcels_writer.hasError() != QgsVectorFileWriter.NoError:
    print "Error when creating shapefile"

agriculture_patch_count = 0

for filename in os.listdir(PARCELS_PATH):
    # process only the appropriate clipped parcels files
    if filename.endswith(".shp") and filename.startswith("Clipped_Parcel"):
        # load the parcel vector layer
        parcels_layer = iface.addVectorLayer(os.path.join(PARCELS_PATH,filename), filename, "ogr")
        if parcels_layer:
            print "Working on " + filename
        else:
            print "Layer failed to load: " + filename
        
        # make sure the first attribute holds LULC field
        first_field = parcels_layer.attributeDisplayName(0)
        if not first_field == "LULC":
            print "Unexpected field instead of LULC: "+ first_field
        else:
            # create missing fields in clipped parcels attribute table
            parcels_layer.startEditing()
            parcels_layer.dataProvider().addAttributes(
                            [QgsField(_PARCEL_FIELD, QVariant.Int),
                             QgsField(_PATCH_FIELD, QVariant.Int)])
            parcels_layer.updateFields()
            
            # extract parcel_id from filename
            parcel_id = filename.strip(".shp").strip("Clipped_Parcels_")
            print "Parcel ID: " + parcel_id
            
            # loop all features and update their attributes
            for feature in parcels_layer.getFeatures():
                feature[_PARCEL_FIELD] = parcel_id
                if (feature[_LULC_FIELD] == 20) or (feature[_LULC_FIELD] == 21):
                    agriculture_patch_count +=1
                    feature[_PATCH_FIELD] = agriculture_patch_count
                else:
                    feature[_PATCH_FIELD] = 0
                print "Patch ID: ", feature[_PATCH_FIELD]
                # keep the record of anomalies
                area = feature.geometry().area()/(3.28*3.28)
                perimeter = feature.geometry().length()/3.28
                if (feature[_AREA_FIELD]<area) or (feature[_PERIMETER_FIELD]<perimeter):
                    print "Area: %f -> %f" % (feature[_AREA_FIELD],area)
                    print "Perimeter: %f -> %f" % (feature[_PERIMETER_FIELD],perimeter)
                # update area and perimeter with current values
                feature[_AREA_FIELD] = area
                feature[_PERIMETER_FIELD] = perimeter
                # add feature to merged parcels file
                merged_parcels_writer.addFeature(feature)
                parcels_layer.updateFeature(feature)
            parcels_layer.commitChanges()
        
# delete the writer to flush features to disk
del merged_parcels_writer

# add new layer to the legend
iface.addVectorLayer(MERGED_PARCELS_PATH, "Merged_Parcels", "ogr")

print 'Processing complete.'
