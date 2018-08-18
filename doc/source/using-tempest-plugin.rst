====================
using tempest plugin
====================

The networking-spp has tempest plugin.

This document explain how to install tempest plugin with devstack.

Requirements
============

The networking-spp tempest plugin has some environmental requirements.

Control Node
------------

Requreiments for the networking-spp tempest plugin are nothing.

Compute Node
------------

* 2 or more compute nodes.
* 2 NIC used for SPP of each compute node.
* 6 ore more CPU cores used for SPP.
* Enough ram to allocate to hugepage for SPP and an instance used for the
  networking-spp tempest plugin. A disk image used for tempest requires 4GB ram.

Settings
========

General settings of devstack is written in _installation.
This section explains about additional settings.

.. _installation: installation.rst


Control Node
------------

Add the following settings to local.conf before running stack.sh.

Note that it is a fragment extracted only for the networking-spp tempest
plugin::

  [[local|localrc]]

  DEFAULT_IMAGE_NAME=ubuntu-dpdk 

  enable_plugin neutron-tempest-plugin https://github.com/openstack/neutron-tempest-plugin master

Note that the interface name for a flat network should be phys1.
And, the interface name for a vlan network should be phys2.

Compute Node
------------

Additional settings for the networking-spp tempest plugin are nothing.


Installing
==========

Run stack.sh according to _installation.

.. _installation: installation.rst

Our devstack script will create and register a disk image and create a flavor
for testing when the tempest service is enabled.
It takes a little long time.


Running tests
=============

If the installation is successful, you can confirm the networking-spp tempest
plugin by the following command::

  $ tempest list-plugins
  +----------------+----------------------------------------------------------------+
  |      Name      |                           EntryPoint                           |
  +----------------+----------------------------------------------------------------+
  | networking_spp | networking_spp.tests.tempest.plugin:NetworkingSppTempestPlugin |
  +----------------+----------------------------------------------------------------+

And this test is able to run by tempest command.
