# Sentinel2Processing_PAGAF
This repository contains the scripts for a geoprocessing workflow in Python for generating Nitrogen Sufficiency Index (SI) geotiffs from a set of 17 Sentinel-2 images collected over Adair County, IA throughout the 2017 corn season (03/2017 - 09/2017). These geotiffs will be used to inform farmers how much Nitrogen to give to their corn in NLT's open source PAGAF web application (https://pagaf.nltmso.com/), depending on how far along they are in the growing season.

## Data
In order to run the code, the user will need to download the data in Google Drive [here](https://drive.google.com/drive/folders/1Z-Lx7nn8cJ75duBPO8Hxho4jfQkWxyfn?usp=sharing) and store it in the corresponding folders (AdairIA, S2).

## Instructions:
1. Download the Google Drive data at the link above
2. Once data is downloaded, install requirements.txt in conda environment with Python3.7
3. To run the program to process all S2 images: In terminal, cd to repository, then run: `python3 run.py`
5. To run the Jupyter Notebook: In terminal, cd to repository, then run: `jupyter notebook` and open S2_CI_SI.ipynb


Output files (Nitrogen Sufficiency Index geotiffs) will be saved in: S2/SI/*
