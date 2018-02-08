#!/bin/bash
cmd=/usr/local/bin/dpdk-devbind.py

sudo bash -c "echo 1024 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages"
sudo modprobe uio
sudo modprobe uio_pci_generic
sudo modprobe vfio_iommu_type1
sudo ${cmd} -b uio_pci_generic 0000:00:04.0
sudo ${cmd} --status
