import os
from modules import estimateincludepaths as eip
sources = eip.source_files(r'..\components\ARM.CMSIS-FreeRTOS.10.2.0')
for file in sources:
    if eip.identify_main(file):
        print(file)
