#!/bin/bash
sudo modprobe -rv spi_ft232h
make
sudo make modules_install
sudo modprobe spi-ft232h
sudo depmod -a