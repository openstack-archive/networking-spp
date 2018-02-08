#!/bin/bash

home_dir=$PWD
if [ $# -eq 1 ]; then
    home_dir=$1/devstack/image
fi

dpdk_ver=dpdk-17.11
dpdk_dir=$home_dir/$dpdk_ver
tempest_file=$dpdk_dir/x86_64-native-linuxapp-gcc/app/testpmd
devbind_file=$dpdk_dir/usertools/dpdk-devbind.py

dpdkapp_dir=$home_dir/../../networking_spp/tests/dpdk-app/l2_ping_pong/
dpdkapp_file=$dpdkapp_dir/build/app/l2_ping_pong

function build_dpdk() {
    sudo apt-get install -y libnuma-dev
    sudo apt-get install -y linux-generic
    sudo apt-get install -y gcc-multilib
    cd $home_dir
    wget http://fast.dpdk.org/rel/$dpdk_ver.tar.gz
    tar xvzf $dpdk_ver.tar.gz
    export RTE_SDK=$home_dir
    export RTE_TARGET=x86_64-native-linuxapp-gcc
    cd $dpdk_dir
    make config T=$RTE_TARGET
    sudo make
    ln -s -f build $RTE_TARGET
}

function build_dpdk_app() {
    cd $dpdkapp_dir
    RTE_SDK=$dpdk_dir make

}

function build_image() {
    sudo apt install -y qemu-utils kpartx
    sudo apt install -y python-pip
    sudo pip install virtualenv
    cd $home_dir
    mkdir dib
    cd dib
    virtualenv env
    source env/bin/activate
    git clone https://git.openstack.org/openstack/diskimage-builder
    cd diskimage-builder
    pip install -e .
    cd ../../
    mkdir dib/diskimage-builder/diskimage_builder/elements/install-bin/bin
    cp -a $devbind_file dib/diskimage-builder/diskimage_builder/elements/install-bin/bin
    cp -a $dpdkapp_file dib/diskimage-builder/diskimage_builder/elements/install-bin/bin
    cp -a files/dpdk_setup.sh dib/diskimage-builder/diskimage_builder/elements/install-bin/bin
    cp -a files/init-scripts dib/diskimage-builder/diskimage_builder/elements/dib-init-system/
    disk-image-create ubuntu vm -p python -p make -p coreutils -p gcc -p gcc-multilib -p linux-generic
}

function cleanup() {
    sudo rm -rf $home_dir/dib
    sudo rm -rf $dpdk_dir
    sudo rm -rf $home_dir/image.d
    sudo rm -rf $dpdk_dir.tar.gz

}

sudo apt-get update
build_dpdk
build_dpdk_app
build_image
cleanup
