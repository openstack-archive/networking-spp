===============================
networking-spp
===============================

Neutron ML2 mechanism driver for Soft Patch Panel

This provides ML2 mechanism driver and agent which makes high speed
communication using Soft Patch Panel (SPP) possible in the OpenStack
environment.

* Free software: Apache license
* Source: https://github.com/openstack/networking-spp
* Bugs: https://bugs.launchpad.net/networking-spp

Introduction
============

SPP_ provides a high speed
communication mechanism using DPDK.  When this driver is used, the VM
and the physical NIC are connected by vhostuser via SPP, and are
transfrerred at high speed without going through the kernel or the virtual
switch.

.. _SPP: https://github.com/ntt-ns/Soft-Patch-Panel

::

            compute node
  +-------------------------------+
  |              VM               |
  |         +----------+          |
  |         |          |          |
  |         |  +----+  |          |
  |         +--|vnic|--+          |
  |            +----+             |
  |              ^ |              |
  |    SPP       | |              |
  |  +-----------| |-----------+  |
  |  |           | |           |  |
  |  |           | | vhostuser |  |
  |  |           | |           |  |
  |  +-----------| |-----------+  |
  |              | |              |
  |              | v              |
  |            +-----+            |
  +------------| NIC |------------+
               +-----+

Comparison with SR-IOV
----------------------

SR-IOV is used to realize high speed communication between the VM and
the phsical NIC too. Compared with SR-IOV, it achieves equivalent
performance and there is an advantage that VM does not need to be
conscious of physical NIC.

Warning
-------

This driver does not enable full function of SPP in the OpenStack
environment. For example, wiring between ports can not be freely
changed. Wiring is done in a predetermined pattern on the compute
node.

For details, see architecture_.

.. _architecture: doc/source/architecture.rst

Assumed environment
===================

SPP is assumed to be used as a high speed communication path between
VMs, and is not used for VM operation.
Therefore a normal network (ex. linuxbdidge) is required for operation
of VM (login, metadata acquisition, etc.).
When VM is started, ordinary network is specified first, and SPP network
is specified as second and subsequent networks.

::

        control node          compute node     compute node  ...
   ---------+----------------------+----------------+-------  for control network
            |                      |                |         and for VM operation
  +---------+-------------+  +-----+-------+  +-----+-------+ (using linuxbridge with
  |                       |  |             |  |             |  vxlan for example)
  |+----------+ +--------+|  |+----+ +----+|  |+----+ +----+|
  ||dhcp-agent| |l3-agent||  || VM | | VM ||  || VM | | VM ||
  |+----------+ +--------+|  |+----+ +----+|  |+----+ +----+|
  |                       |  |  |      |   |  |  |      |   |
  +-----------------------+  +--+------+---+  +--+------+---+
                                |      |         |      |
                             ---+----------------+------------  for SPP network
                                       |                |
                             ----------+----------------+-----

Restrictions
============

* flat or vlan type network only available.
* security group is not supported.
  It does not cause an error as an API, but it is ignored even if it is set.
* VM using an SPP network can not perform live migration.
* communication between VMs on the same host is not available. That is,
  it can not be looped back inside the host, and only communicates via
  an external switch.

Installation
============

It supports installation with devstack.

See installation_.

.. _installation: doc/source/installation.rst

Usage
=====

See usage_.

.. _usage: doc/source/usage.rst

