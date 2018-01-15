========
devstack
========

Parameter list
--------------

A list of devstack parameters added by networking-spp is shown with a brief description.

Details will be explained separately into some categories later.

+-------------------------+------------------------------+-------------------------------------------+
| parameter               | default                      | content                                   |
+=========================+==============================+===========================================+
| DPDK_GIT_REPO           | http://dpdk.org/git/dpdk     | DPDK repository                           |
+-------------------------+------------------------------+-------------------------------------------+
| DPDK_GIT_TAG            | v17.11                       | branch(tag) of DPDK                       |
+-------------------------+------------------------------+-------------------------------------------+
| DPDK_DIR                | $DEST/DPDK-$DPDK_GIT_TAG     | DPDK installation directory               |
+-------------------------+------------------------------+-------------------------------------------+
| RTE_TARGET              | x86_64-native-linuxapp-gcc   | DPDK build target                         |
+-------------------------+------------------------------+-------------------------------------------+
| RTE_SDK                 | $DPDK_DIR                    | Used when building SPP                    |
+-------------------------+------------------------------+-------------------------------------------+
| SPP_GIT_REPO            | http://dpdk.org/git/apps/spp | SPP repository                            |
+-------------------------+------------------------------+-------------------------------------------+
| SPP_GIT_TAG             | $DPDK_GIT_TAG                | branch(tag) of SPP                        |
+-------------------------+------------------------------+-------------------------------------------+
| SPP_DIR                 | $DEST/SPP-$SPP_GIT_TAG       | SPP installation directory                |
+-------------------------+------------------------------+-------------------------------------------+
| SPP_DPDK_BUILD_SKIP     | $OFFLINE                     | specify to skip DPDK/SPP build            |
+-------------------------+------------------------------+-------------------------------------------+
| SPP_ALLOCATE_HUGEPAGES  | False                        | specify to allocate hugepages in devstack |
+-------------------------+------------------------------+-------------------------------------------+
| SPP_NUM_HUGEPAGES       | 2048                         | number of hugepages to allocate           |
+-------------------------+------------------------------+-------------------------------------------+
| SPP_HUGEPAGE_MOUNT      | /mnt/huge                    | mount directory for hugepage              |
+-------------------------+------------------------------+-------------------------------------------+
| SPP_MODE                | compute                      | 'compute' or 'control'                    |
+-------------------------+------------------------------+-------------------------------------------+
| DPDK_PORT_MAPPINGS      | <must be specified>          | configration information                  |
+-------------------------+------------------------------+-------------------------------------------+
| SPP_PRIMARY_SOCKET_MEM  | 1024                         | --socket-mem of spp_primary               |
+-------------------------+------------------------------+-------------------------------------------+
| SPP_PRIMARY_CORE_MASK   | 0x02                         | core_mask of spp_primary                  |
+-------------------------+------------------------------+-------------------------------------------+
| SPP_PRIMATY_SOCK_PORT   | 5555                         | socket port for spp_primary               |
+-------------------------+------------------------------+-------------------------------------------+
| SPP_SECONDARY_SOCK_PORT | 6666                         | socket port for spp_vf                    |
+-------------------------+------------------------------+-------------------------------------------+
| SPP_HOST                | $(hostname -s)               | host name                                 |
+-------------------------+------------------------------+-------------------------------------------+
| ETCD_HOST               | $SERVICE_HOST                | etcd host                                 |
+-------------------------+------------------------------+-------------------------------------------+
| ETCD_PORT               | 2379                         | etcd port                                 |
+-------------------------+------------------------------+-------------------------------------------+

Required parameter for control node
-----------------------------------

SPP_MODE
++++++++

Specify 'control' for control node. Note that this parameter is not necessary
to specify for compute node since the default value is 'compute'.

This is the only parameter that needs to be specified for control node.

Required parameters for compute node
------------------------------------

DPDK_PORT_MAPPINGS
++++++++++++++++++

Specify configration information for the NICs assigned for SPP.

The format for each NIC is as follows::

  <PCI address>#<physical_network>#<number of vhostusers>#<core_mask>

PCI address
  PCI address of the NIC.

physical_network
  physical_network of the neutron network corresponding to the NIC.

number of vhostusers
  number of vhostusers to be allocated on the NIC.

core_mask
  core_mask of the spp_vf process corresponding to the NIC.
  This is a parameter passed directly to the DPDK option '-c' of spp_vf.
  See SPP or DPDK document for details. See example_ also.

.. _example: architecture.rst#example-of-core-mask-setting-of-spp-processes

As a whole, specify all the NICs for SPP by separating them with a comma(,)
in order of PCI address (i.e. in order of DPDK port).

example::

  DPDK_PORT_MAPPINGS=00:04.0#phys1#2#0xfe,00:05.0#phys2#2#xfc02

SPP_PRIMARY_SOCKET_MEM
++++++++++++++++++++++

Specify the amount of hugepage (MB) used by SPP. In the case of multiple
numa nodes, specify the assignment for each node with a comma.
This is a parameter passed directly to the DPDK option '--socket-mem' of
spp_primary. See SPP or DPDK document for details.

example::

  SPP_PRIMARY_SOCKET_MEM=1024,1024

SPP_PRIMARY_CORE_MASK
+++++++++++++++++++++

core_mask of the spp_primary process. This is a parameter passed
directly to the DPDK option '-c' of spp_primary.
See SPP or DPDK document for details. See example_ also.

Option parameters for compute node
----------------------------------

SPP_ALLOCATE_HUGEPAGES
++++++++++++++++++++++

It is recommended that hugepages are allocated at kernel boot, but it
can be done at devstack execution. If you want to allocate hugepages
when running devstack, set this parameter to True.

SPP_NUM_HUGEPAGES
+++++++++++++++++

The number of hugepages to be allocated **for each numa node**.
Note that the size of hugepage is default hugepage size.
It must be specified and is only valid when SPP_ALLOCATE_HUGEPAGES is True.

SPP_HUGEPAGE_MOUNT
++++++++++++++++++

Specify the mount point of hugepage for SPP. It is better to separate
the mount point of hugepage for SPP and for VM. Normally, there is
no problem with default(/mnt/huge). Devstack mounts it at execution
if necessary, so you do not have to mount them beforehand.

Other parameters
----------------

Normally, other parameters do not need to be specified, so the
detail explanation is omitted.

Parameters related to config
----------------------------

The following parameters are reflected in the configuration.
The configuration parameters corresponding to each parameter
are shown below.

SPP_PRIMATY_SOCK_PORT
  [spp] primary_sock_port

SPP_SECONDARY_SOCK_PORT
  [spp] secondary_sock_port

ETCD_HOST
  [spp] etcd_host

ETCD_PORT
  [spp] etcd_port
