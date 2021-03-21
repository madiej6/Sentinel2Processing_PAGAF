import time
from bs4 import BeautifulSoup as bs
import lxml
import sys, os, struct
import osgeo.gdal as gdal
import rasterio
from rasterio import plot
import numpy as np
import glob
import fiona


# this function normalizes numpy arrays to range from 0 - 1 between the true min and max values
def normalize(array):
    """Normalizes numpy arrays into scale 0.0 - 1.0"""
    array_min, array_max = array[~np.isnan(array)].min(), array[~np.isnan(array)].max()
    return ((array - array_min)/(array_max - array_min))



def main():
    t = time.time()

    # scan for S2 dirs in the S2 folder
    IMGs_LIST = glob.glob("S2/*SAFE")
    for IMG_DATA in IMGs_LIST:
        IMG_NAME = IMG_DATA.split("MSIL1C_")[1].split('.SAFE')[0]
        print('Image Name: {}'.format(IMG_NAME))

        granulesubdir = glob.glob(IMG_DATA+"/GRANULE/*")[0]

        # get filenames of each band
        band2 = glob.glob(granulesubdir+"/IMG_DATA/*B02.jp2")[0] #blue
        band3 = glob.glob(granulesubdir+"/IMG_DATA/*B03.jp2")[0] #green
        band4 = glob.glob(granulesubdir+"/IMG_DATA/*B04.jp2")[0] #red
        band5 = glob.glob(granulesubdir+"/IMG_DATA/*B05.jp2")[0] #rededge1
        band8 = glob.glob(granulesubdir+"/IMG_DATA/*B08.jp2")[0] #nir

        # open band imgs w/ rasterio
        band2_rio = rasterio.open(band2, driver='JP2OpenJPEG') #blue
        band3_rio = rasterio.open(band3, driver='JP2OpenJPEG') #green
        band4_rio = rasterio.open(band4, driver='JP2OpenJPEG') #red
        band5_rio = rasterio.open(band5, driver='JP2OpenJPEG') #rededge1
        band8_rio = rasterio.open(band8, driver='JP2OpenJPEG') #nir

        # open True Color Image (TCI) for preview of scene
        tci = glob.glob(granulesubdir+"/IMG_DATA/*TCI.jp2")[0]
        tci_rio = rasterio.open(tci, driver='JP2OpenJPEG') #tci

        # read in xml (metadata) file
        ROOT_PATH = IMG_DATA.split('/GRANULE')[0]
        xml = glob.glob(ROOT_PATH+"/MTD*.xml")[0]

        with open(xml, "r") as file:
            content = file.readlines()
            content = "".join(content)
            bs_content = bs(content, "lxml")

        # scan xml file for cloud coverage percentage
        result = bs_content.find("cloud_coverage_assessment")
        cloud_pct = float(result.text)
        print('Cloud Coverage: {}%'.format(cloud_pct))

        # create 5-band stack (blue, green, red, red edge, nir)
        output = r"S2/OUTPUT/{}_S2stack_5bands.tif".format(IMG_NAME)
        os.system('gdal_merge.py -o ' + output + ' -separate -co PHOTOMETRIC=RGB ' + band2 + ' ' + band3 + ' ' + band4 + ' ' + band5 + ' ' + band8)

        # define cloud mask file path and shp output file path
        cloud_gml = IMG_DATA.split("/IMG")[0]+"/QI_DATA/MSK_CLOUDS_B00.gml"
        cloud_shp = IMG_DATA.split("/IMG")[0]+"/QI_DATA/MSK_CLOUDS_B00.shp"

        # convert gml cloud mask to shapefile
        cmd = """ogr2ogr -f 'ESRI Shapefile' {} {} """.format(cloud_shp, cloud_gml)
        os.system(cmd)

        # burn cloud mask into raster
        cmd = """gdal_rasterize -b 1 -b 2 -b 3 -b 4 -b 4 -burn 0 -burn 0 -burn 0 -burn 0 -burn 0 -l MSK_CLOUDS_B00 {} {}""".format(cloud_shp, output)
        os.system(cmd)


        # import corn mask shapefile
        cornmask_shp = r"AdairIA/CLUs_MajorityCorn_AdairIA.shp"

        #shape = fiona.open(cornmask_shp)
        with fiona.open(cornmask_shp, "r") as shapefile:
            shapes = [feature["geometry"] for feature in shapefile]

        # using corn mask on 5band stack geotiff
        from rasterio.mask import mask
        with rasterio.open(output) as src:
            out_image, out_transform = rasterio.mask.mask(src, shapes, all_touched=False, invert=False, nodata=0, crop = True, pad = True)
            out_meta = src.meta

        # grabbing metadata from 5band stack so when i export the corn masked image it contains the same metadata
        out_meta.update({"driver": "GTiff",
                         "height": out_image.shape[1],
                         "width": out_image.shape[2],
                         "transform": out_transform})

        # export corn-masked 5band stack to geotiff
        output_cornmask = r"S2/OUTPUT/{}_S2stack_5bands_cornmask.tif".format(IMG_NAME)

        with rasterio.open(output_cornmask, "w", **out_meta) as dest:
            dest.write(out_image)

        # get metadata of mosaic for sanity check
        stack_rio = rasterio.open(output_cornmask)
        stack_rio.meta

        # read in red edge and nir bands as numpy arrays
        rededge = stack_rio.read(4).astype('float64') #rededge1
        nir = stack_rio.read(5).astype('float64') #nir

        # set 0's to nan for math coming up
        rededge[rededge==0] = np.nan
        nir[nir==0] = np.nan



        # calculate chlorophyll index (CI): NIR/Red Edge - 1
        CI = np.where((nir+rededge)==0.0,0,((nir/rededge) - 1))


        #export CI geotiff
        CI_img = rasterio.open(r"S2/OUTPUT/{}_CI.tif".format(IMG_NAME), 'w', driver='Gtiff',
                              width = stack_rio.width,
                              height = stack_rio.height,
                              count = 1, crs = stack_rio.crs,
                              transform = stack_rio.transform,
                              dtype='float64')
        CI_img.write(CI,1)
        CI_img.close()

        # print min and max CI pixel values
        minCI = CI[~np.isnan(CI)].min()
        maxCI = CI[~np.isnan(CI)].max()

        # open CI image in rasterio
        CI_img = rasterio.open(r"S2/OUTPUT/{}_CI.tif".format(IMG_NAME))
        CIband = CI_img.read(1).astype('float64') #CI

        # normalize CI
        CIband_normalized = normalize(CIband)

        #export normalized CI (NCI) image as geotiff
        NCI_img = rasterio.open(r"/Users/Madeline/Projects/PAGAF/S2/NCI/{}_NCI.tif".format(IMG_NAME), 'w', driver='Gtiff',
                              width = CI_img.width,
                              height = CI_img.height,
                              count = 1, crs = CI_img.crs,
                              transform = CI_img.transform,
                              dtype='float64')
        NCI_img.write(CIband_normalized,1)
        NCI_img.close()

        # open NCI image in rasterio
        NCI_rio = rasterio.open(r"S2/NCI/{}_NCI.tif".format(IMG_NAME))
        NCIband = NCI_rio.read(1).astype('float64') #NCI

        # bottom limit of Sufficiency Index - 40th percentile
        bottomlim = np.percentile(NCIband[~np.isnan(NCIband)], 40)
        # top limit of Sufficiency Index - 90th percentile
        toplim = np.percentile(NCIband[~np.isnan(NCIband)], 90)

        # create Sufficiency Index (SI) array
        SI_ = np.where(NCIband < bottomlim, np.nan, NCIband) # make all values less than 40th percentile nan
        SI = np.where(NCIband > toplim, 1, SI_) # make all values greater than 90th percentile 1

        #export SI array to geotiff
        SI_img = rasterio.open(r"/Users/Madeline/Projects/PAGAF/S2/OUTPUT/{}_SI.tif".format(IMG_NAME), 'w', driver='Gtiff',
                              width = CI_img.width,
                              height = CI_img.height,
                              count = 1, crs = CI_img.crs,
                              transform = CI_img.transform,
                              dtype='float64')
        SI_img.write(SI,1)
        SI_img.close()

        # open SI image in rasterio
        SI_rio = rasterio.open(r"S2/OUTPUT/{}_SI.tif".format(IMG_NAME))
        SI = SI_rio.read(1).astype('float64') #SI

        # normalize SI array
        NSI = normalize(SI)

        #export normalized SI to geotiff
        NSI_img = rasterio.open(r"/Users/Madeline/Projects/PAGAF/S2/SI/{}_SI.tif".format(IMG_NAME), 'w', driver='Gtiff',
                              width = CI_img.width,
                              height = CI_img.height,
                              count = 1, crs = CI_img.crs,
                              transform = CI_img.transform,
                              dtype='float64')
        NSI_img.write(NSI,1)
        NSI_img.close()

        # print total run time in seconds
        elapsed = time.time() - t
        print("total run time (seconds): ", elapsed)

    return

if __name__ == "__main__":
    main()
