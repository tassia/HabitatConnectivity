from qgis.utils import iface
from PyQt4.QtCore import QVariant
from geopandas import GeoSeries
from shapely.wkb import loads
from qgis.core import *

# paths to habitat block and parcels files
LULC_PATH = "/media/tassia/rouge/ENVR401/Richford-GIS/Ranked_Parcels/LULC_Missisquoi_Richford_HabitatBlock.shp"
PATCHES_PATH = "/media/tassia/rouge/ENVR401/Richford-GIS/Ranked_Parcels/Merged_Parcels_Agriculture.shp"
HABBLOCK_PATH = "/media/tassia/rouge/ENVR401/Richford-GIS/Ranked_Parcels/Habitat_Blocks.shp"

lulc_layer = iface.addVectorLayer(LULC_PATH, "LULC_Richford_Wild", "ogr")
patches_layer = iface.addVectorLayer(PATCHES_PATH, "Agriculture_patches", "ogr")

# Original attributes from Patches map
_LULC_FIELD = 'LULC'
_AREA_FIELD = 'Area'
_PERIMETER_FIELD = 'Perimeter'
_PARCEL_FIELD = 'Parcel_ID'
_PATCH_FIELD = 'Patch_ID'
_SOURCE_PATCH_FIELD = 'Source_ID'

# New attributes to be added
_NEIGHBORS_FIELD = 'NEIGHBORS'
_HABITAT_BLOCK_AREA_FIELD = 'HABBLOCK_A'
_HABITAT_BLOCK_PERIMETER_FIELD = 'HABBLOCK_P'
_INDEX_R = 'INDEX_R'

class RankedParcel(object):
    def __init__(self, id):
        self.id = id
        self.best_index = 0
        self.patches_list = []
        
    def __repr__(self):
        #ordered_list = ['(%d,%.2f)' % (i.id,i.index_r) for i in sorted(self.patches_list, key= lambda id: id.index_r, reverse=True)]
        ordered_list = [' %d, %.2f' % (i.id,i.index_r) for i in sorted(self.patches_list, key= lambda id: id.index_r, reverse=True)]
        ordered_list_str = ','.join([i for i in ordered_list])
        return '%d,%s' % (self.id, ordered_list_str)
        #return '%d: [%s]' % (self.id, ordered_list_str)
        
    def addPatch(self, patch):
        if patch.index_r > self.best_index:
            self.best_index = patch.index_r
        self.patches_list.append(patch)

class RankedPatch(object):
    def __init__(self, id, index_r):
        self.id = id
        self.index_r = index_r

patches_layer.startEditing()
patches_layer.dataProvider().addAttributes(
        [QgsField(_NEIGHBORS_FIELD, QVariant.String),
         QgsField(_HABITAT_BLOCK_AREA_FIELD, QVariant.Double),
         QgsField(_HABITAT_BLOCK_PERIMETER_FIELD, QVariant.Double),
         QgsField(_INDEX_R, QVariant.Double)])
patches_layer.updateFields()

fields = QgsFields()
fields.append(QgsField(_SOURCE_PATCH_FIELD, QVariant.Int))
fields.append(QgsField(_NEIGHBORS_FIELD, QVariant.String))
fields.append(QgsField(_AREA_FIELD, QVariant.Double))
fields.append(QgsField(_PERIMETER_FIELD, QVariant.Double))

habitat_blocks_writer = QgsVectorFileWriter(HABBLOCK_PATH, "CP1250", fields, QGis.WKBPolygon, QgsCoordinateReferenceSystem("EPSG:102745"), "ESRI Shapefile")

if habitat_blocks_writer.hasError() != QgsVectorFileWriter.NoError:
    print "Error when creating shapefile"

# Create dictionaries of all features
patches_dict = {f.id(): f for f in patches_layer.getFeatures()}
lulc_dict = {f.id(): f for f in lulc_layer.getFeatures()}

# Build a spatial index for all features
index = QgsSpatialIndex()
for f in patches_dict.values():
    index.insertFeature(f)
for f in lulc_dict.values():
    index.insertFeature(f)

# Initialize rank dictionary
rank_dict = {}

# Loop through all features and find features that touch each feature
for f in patches_dict.values():
    print 'Working on patch %s' % f[_PATCH_FIELD]
    geom = f.geometry()
    # Find all features that intersect the bounding box of the current feature.
    # We use spatial index to find the features intersecting the bounding box
    # of the current feature. This will narrow down the features that we need
    # to check neighboring features.
    intersecting_ids = index.intersects(geom.boundingBox())
    
    # Initalize neighbors list
    neighbor_patches = []
    neighbor_patches_geom = []
    
    for intersecting_id in intersecting_ids:
        # Look up the feature from the lulc dictionary
        intersecting_f = lulc_dict[intersecting_id]
         
        # For our purpose we consider a feature as 'neighbor' if it touches or
        # intersects a feature. We use the 'disjoint' predicate to satisfy
        # these conditions. So if a feature is not disjoint, it is a neighbor.
        if (f != intersecting_f and not intersecting_f.geometry().disjoint(geom)):
            neighbor_patches.append(str(intersecting_f[_LULC_FIELD]))
            neighbor_patches_geom.append(loads(intersecting_f.geometry().asWkb()))

    # add the source patch to neighbors just before creating the habitat block
    neighbor_patches_geom.append(loads(geom.asWkb()))
        
    habitat_block_series = GeoSeries(neighbor_patches_geom)
    habitat_block_geom = habitat_block_series.unary_union
        
    f[_NEIGHBORS_FIELD] = ','.join(neighbor_patches)
    f[_HABITAT_BLOCK_AREA_FIELD] = habitat_block_geom.area/(3.28*3.28)
    f[_HABITAT_BLOCK_PERIMETER_FIELD] = habitat_block_geom.length/3.28
    f[_INDEX_R] = (geom.area()/(3.28*3.28))/f[_HABITAT_BLOCK_PERIMETER_FIELD]
    
    if f[_PARCEL_FIELD] not in rank_dict:
        rank_dict[f[_PARCEL_FIELD]] = RankedParcel(f[_PARCEL_FIELD])
        #print dir(rank_dict[f[_PARCEL_FIELD]])
    
    patch = RankedPatch(f[_PATCH_FIELD],f[_INDEX_R])
    rank_dict[f[_PARCEL_FIELD]].addPatch(patch)
    #print rank_dict[f[_PARCEL_FIELD]].best_index
    
    # new habitat_block feature
    habblock_feature = QgsFeature()
    habblock_feature.setGeometry(QgsGeometry.fromWkt(habitat_block_geom.to_wkt()))
    habblock_feature.setAttributes([f[_PATCH_FIELD], f[_NEIGHBORS_FIELD], f[_HABITAT_BLOCK_AREA_FIELD], f[_HABITAT_BLOCK_PERIMETER_FIELD]])

    habitat_blocks_writer.addFeature(habblock_feature)

    # Update the layer with new attribute values.
    patches_layer.updateFeature(f)

# Save all changes to 
patches_layer.commitChanges()

print "Parcel_ID, Index_R, [patches_list]"
for key in sorted(rank_dict, key= lambda id: rank_dict[id].best_index, reverse=True):
    print rank_dict[key]

# delete the writer to flush features to disk
del habitat_blocks_writer

# add new layer to the legend
iface.addVectorLayer(HABBLOCK_PATH, "Habitat_Blocks", "ogr")

print 'Processing complete.'
