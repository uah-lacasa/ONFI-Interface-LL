# Introduction

The project **ONFI-Interface-LL** is interfacing code for Open NAND Flash Complaint (ONFI) flash memory chip. The codes used in this project are influenced by codes from *dumpflash* project that can be found at https://github.com/ohjeongwook/dumpflash. In fact, we reuse the code to interface the NAND flash chips with the FTDI chip. This project, however, aims to perform analysis of data, Bit Error Rate (BER) and so on. Since this project does not concern file system, we trim the codes for file handling to streamline the code.

Following are some of the results of reading ONFI Page:
*