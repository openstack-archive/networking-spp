============================================
Customization of the components construction
============================================

Non default configurations can be defined in the yaml file
whose path should be passed via the ``SPP_COMPONENT_CONF``
variable. For example, you will need the file for the following
use cases:

* Using a common core among the components.
* Omitting forwarders.

Definition of the yaml
======================

top level parameters
--------------------

+-----+-----------------------+
| key | value                 |
+=====+=======================+
| vf  | array of spp_vf info  |
+-----+-----------------------+

spp_vf info
-----------

+------------+-------------------------+
| key        | value                   |
+============+=========================+
| components | array of component info |
+------------+-------------------------+

component info
--------------

+---------+-------------------+
| key     | value             |
+=========+===================+
| core    | core id           |
+---------+-------------------+
| name    | component name    |
+---------+-------------------+
| type    | component type    |
+---------+-------------------+
| rx_port | array of rx ports |
+---------+-------------------+
| tx_port | array of tx ports |
+---------+-------------------+

Example 1: core duplication
===========================

This example is that component construction is same as default
but saving cores.

local.conf::

  DPDK_PORT_MAPPINGS=00:04.0#phys1#2#0x3e,00:05.0#phys2#2#x3c02
  SPP_COMPONENT_CONF=/usr/local/etc/sample_1.yaml

sample_1.yaml::

  vf:
  - components:
    - core: 2
      name: forward_0_tx
      rx_port: ['ring:0']
      tx_port: ['vhost:0']
      type: forward
    - core: 2
      name: forward_0_rx
      rx_port: ['vhost:0']
      tx_port: ['ring:1']
      type: forward
    - core: 3
      name: forward_1_tx
      rx_port: ['ring:2']
      tx_port: ['vhost:1']
      type: forward
    - core: 3
      name: forward_1_rx
      rx_port: ['vhost:1']
      tx_port: ['ring:3']
      type: forward
    - core: 4
      name: classifier
      rx_port: ['phy:0']
      tx_port: ['ring:0', 'ring:2']
      type: classifier_mac
    - core: 5
      name: merger
      rx_port: ['ring:1', 'ring:3']
      tx_port: ['phy:0']
      type: merge
  - components:
    - core: 10
      name: forward_2_tx
      rx_port: ['ring:4']
      tx_port: ['vhost:2']
      type: forward
    - core: 10
      name: forward_2_rx
      rx_port: ['vhost:2']
      tx_port: ['ring:5']
      type: forward
    - core: 11
      name: forward_3_tx
      rx_port: ['ring:6']
      tx_port: ['vhost:3']
      type: forward
    - core: 11
      name: forward_3_rx
      rx_port: ['vhost:3']
      tx_port: ['ring:7']
      type: forward
    - core: 12
      name: classifier
      rx_port: ['phy:1']
      tx_port: ['ring:4', 'ring:6']
      type: classifier_mac
    - core: 13
      name: merger
      rx_port: ['ring:5', 'ring:7']
      tx_port: ['phy:1']
      type: merge


.. _resource-saving-example-2:

Example 2: omitting forwarders
==============================

This example is that there is no forwarder as shown the following
diagram.

::

                                              +-----------+
                                              |           |
                                        +-----+> rx       |
                                        |     |           |
                                        |     | vhostuser |
  +------+                              |     |           |
  |      |          +------------+ -----+  +--+- tx       |
  |  tx -+--------->| classifier |         |  |           |
  |      |          +------------+ -----+  |  +-----------+
  | NIC  |                              |  |
  |      |          +------------+ <-------+  +-----------+
  |  rx <+----------| merge      |      |     |           |
  |      |          +------------+ <--+ +-----+> rx       |
  +------+                            |       |           |
                                      |       | vhostuser |
                                      |       |           |
                                      +-------+- tx       |
                                              |           |
                                              +-----------+


local.conf::

  DPDK_PORT_MAPPINGS=00:04.0#phys1#2#0xc2,00:05.0#phys2#2#xc002
  SPP_COMPONENT_CONF=/usr/local/etc/sample_2.yaml


sample_2.yaml::

  vf:
  - components:
    - core: 6
      name: classifier
      rx_port: ['phy:0']
      tx_port: ['vhost:0', 'vhost:1']
      type: classifier_mac
    - core: 7
      name: merger
      rx_port: ['vhost:0', 'vhost:1']
      tx_port: ['phy:0']
      type: merge
  - components:
    - core: 14
      name: classifier
      rx_port: ['phy:1']
      tx_port: ['vhost:2', 'vhost:3']
      type: classifier_mac
    - core: 15
      name: merger
      rx_port: ['vhost:2', 'vhost:3']
      tx_port: ['phy:1']
      type: merge
