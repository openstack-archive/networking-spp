==============
Architecture
==============

Processes on compute node
=========================

There are three kind of processes on a compute node.

spp_primary
  It is a DPDK primary process provided by SPP.
  It initializes resources for DPDK on the host.

spp_vf
  It is a DPDK secondary process provided by SPP.
  It transfers between VM and physical NIC.
  The spp_vf process is executed for each physical NIC.
  vhostuser is used to connect with VM. The number of vhostusers
  to allocate for each physical NIC is specified in the configuration.

spp-ctl
  It is a SPP controller with a REST like web API.
  It maintains the connections form the SPP processes and at
  the same time exposes the API for the user to request for the
  SPP processes.

spp-agent
  It requests the operation of spp_vf to spp-ctl according to
  the request from neutron-server.

::

     compute node
  +------------------------------------------------------------------------------+
  |                                                                              |
  |         VM                      VM                                           |
  |     +----------+       +------------------+                                  |
  |     |          |       |                  |                                  |
  |     |  +----+  |       |  +----+  +----+  |                  spp_primary     |
  |     +--|vnic|--+       +--|vnic|--|vnic|--+                 +-----------+    |
  |        +----+             +----+  +----+                    |           |    |
  |          ^ |                ^ |     ^ |                     +-----------+    |
  |          | |       +--------+ |     | |                                      |
  |          | |       | +--------+     | |                                      |
  |          | |       | |              | |                        spp-ctl       |
  |  spp_vf  | v       | v      spp_vf  | v                     +-----------+    |
  |     +---------------------+    +---------------------+      |           |    |
  |     | +-------+ +-------+ |    | +-------+ +-------+ |      +-----------+    |
  |     | |vhost:0| |vhost:1| |    | |vhost:2| |vhost:3| |                       |
  |     | +-------+ +-------+ |    | +-------+ +-------+ |                       |
  |     |                     |    |                     |        spp-agent      |
  |     |   classifier/merge  |    |   classifier/merge  |      +-----------+    |
  |     +---------------------+    +---------------------+      |           |    |
  |              ^  |                       ^  |                +-----------+    |
  |              |  |                       |  |                                 |
  |              |  v                       |  v                                 |
  |            +------+                   +------+                               |
  +------------|phys:0|-------------------|phys:1|-------------------------------+
               +------+                   +------+

Component composition of spp_vf
===============================

* a 'classifier' component and a 'merge' component per physical NIC.
* two 'forward' components per vhostuser.
* a physical core per component.

::

                                                               +-----------+
                                              +---------+      |           |
                                        +---->| forward |------+> rx       |
                                        |     +---------+      |           |
                                        |                      | vhostuser |
  +------+                              |     +---------+      |           |
  |      |          +------------+ -----+  +--| forward |<-----+- tx       |
  |  tx -+--------->| classifier |         |  +---------+      |           |
  |      |          +------------+ -----+  |                   +-----------+
  | NIC  |                              |  |
  |      |          +------------+ <-------+                   +-----------+
  |  rx <+----------| merge      |      |     +---------+      |           |
  |      |          +------------+ <--+ +---->| forward |------+> rx       |
  +------+                            |       +---------+      |           |
                                      |                        | vhostuser |
                                      |       +---------+      |           |
                                      +-------| forward |<-----+- tx       |
                                              +---------+      |           |
                                                               +-----------+

.. _example-of-core-mask-setting:

Example of core mask setting of spp processes
---------------------------------------------

The concept of core mask of spp_primary and spp_vf that needs to be
specified in the configuration is explained below.

master core
  The least significant bit of core mask of each process indicates the
  master core. Even without occupying the master core, there is no
  problem in terms of performance. You can choose it from the core for
  system services.

core mask of spp_primary
  spp_primary is necessary only for the master core.

number of cores required to occupy spp_vf
  The number of cores that need to be occupied by spp_vf is
  "vhostuser number * 2 (for forward)" + 2 (classifier, merge).
  It is necessary to allocate them so that they do not overlap each
  other between spp_vf.

core mask of spp_vf
  In the core mask of spp_vf, in addition to the above occupancy,
  specify what to use as the master core.

Configuration example
+++++++++++++++++++++

* Both spp_primary and spp_vfs share the master core and use core id 1.
* spp_vf(1) uses two vhostusers and uses core id 2 to 7.
* spp_vf(2) uses two vhostusers and uses core id 10 to 15.

::

  SPP_PRIMARY_CORE_MASK=0x2
  DPDK_PORT_MAPPINGS=00:04.0#phys1#2#0xfe,00:05.0#phys2#2#xfc02

Customization of component construction
---------------------------------------

There is a way to construct components as other than default
explained above.

See :doc:`Customization of the components construction <customization>`
for details.

Communication between server and agent
======================================

etcd is used to store the configuration and usage of vhostuser on each
compute node.
In addition, communication between neutron-server(spp mechanism driver)
and spp-agent is done via etcd.

::

     control node
  +---------------------------------------+
  |                                       |      compute node
  |      neutron-server                   |    +-----------------+
  |     +---------------+                 |    |                 |
  |     |               |      etcd       |    |    spp-agent    |
  |     | +-----------+ |    +-------+    |    |  +-----------+  |
  |     | | spp       |<---->|       |<---------->|           |  |
  |     | | mechanism | |    +-------+    |    |  +-----------+  |
  |     | | driver    | |                 |    |                 |
  |     | +-----------+ |                 |    +-----------------+
  |     |               |                 |
  |     +---------------+                 |
  |                                       |
  +---------------------------------------+

etcd keys
---------

The key list of etcd used by networking-spp is shown below.

=============================================  ======== ===============  =========
key                                            devstack spp mech driver  spp-agent
=============================================  ======== ===============  =========
/spp/openstack/configuration/<host>              C        R                R
/spp/openstack/vhost/<host>/<phys>/<vhost_id>    C        RW               W
/spp/openstack/port_status/<host>/<port id>               CW               RD
/spp/openstack/bind_port/<host>/<port id>                 R                CWD
/spp/openstack/action/<host>/<port id>                    CW               RD
=============================================  ======== ===============  =========

/spp/openstack/configuration/<host>
+++++++++++++++++++++++++++++++++++

Configuration information of each host. It is an array of dict consist of
information for each NIC assigned to SPP.
The order of dict is the port order of DPDK.
The key and value of dict are as follows.

vf
  array of spp_vf info

spp_vf info is as follows.

pci_address
  PCI address of the NIC

physical_network
  physical_network assigned to the NIC

num_vhost
  the number of vhostusers allocated for the NIC

core_mask
  core_mask of spp_vf for the NIC

components
  array of component info

component info is as follows.

core
  core id

type
  component type

name
  component name

tx_port
  array of tx ports

rx_port
  array of rx ports

example(It is shaping for ease of viewing)::

  {
    "vf": [
        {
            "components": [
                {
                    "core": 2,
                    "name": "forward_0_tx",
                    "rx_port": [
                        "ring:0"
                    ],
                    "tx_port": [
                        "vhost:0"
                    ],
                    "type": "forward"
                },
                {
                    "core": 3,
                    "name": "forward_0_rx",
                    "rx_port": [
                        "vhost:0"
                    ],
                    "tx_port": [
                        "ring:1"
                    ],
                    "type": "forward"
                },
                {
                    "core": 4,
                    "name": "forward_1_tx",
                    "rx_port": [
                        "ring:2"
                    ],
                    "tx_port": [
                        "vhost:1"
                    ],
                    "type": "forward"
                },
                {
                    "core": 5,
                    "name": "forward_1_rx",
                    "rx_port": [
                        "vhost:1"
                    ],
                    "tx_port": [
                        "ring:3"
                    ],
                    "type": "forward"
                },
                {
                    "core": 6,
                    "name": "classifier",
                    "rx_port": [
                        "phy:0"
                    ],
                    "tx_port": [
                        "ring:0",
                        "ring:2"
                    ],
                    "type": "classifier_mac"
                },
                {
                    "core": 7,
                    "name": "merger",
                    "rx_port": [
                        "ring:1",
                        "ring:3"
                    ],
                    "tx_port": [
                        "phy:0"
                    ],
                    "type": "merge"
                }
            ],
            "core_mask": "0xfe",
            "num_vhost": 2,
            "pci_address": "00:04.0",
            "physical_network": "phys1"
        },
        {
            "components": [
                {
                    "core": 10,
                    "name": "forward_2_tx",
                    "rx_port": [
                        "ring:4"
                    ],
                    "tx_port": [
                        "vhost:2"
                    ],
                    "type": "forward"
                },
                {
                    "core": 11,
                    "name": "forward_2_rx",
                    "rx_port": [
                        "vhost:2"
                    ],
                    "tx_port": [
                        "ring:5"
                    ],
                    "type": "forward"
                },
                {
                    "core": 12,
                    "name": "forward_3_tx",
                    "rx_port": [
                        "ring:6"
                    ],
                    "tx_port": [
                        "vhost:3"
                    ],
                    "type": "forward"
                },
                {
                    "core": 13,
                    "name": "forward_3_rx",
                    "rx_port": [
                        "vhost:3"
                    ],
                    "tx_port": [
                        "ring:7"
                    ],
                    "type": "forward"
                },
                {
                    "core": 14,
                    "name": "classifier",
                    "rx_port": [
                        "phy:1"
                    ],
                    "tx_port": [
                        "ring:4",
                        "ring:6"
                    ],
                    "type": "classifier_mac"
                },
                {
                    "core": 15,
                    "name": "merger",
                    "rx_port": [
                        "ring:5",
                        "ring:7"
                    ],
                    "tx_port": [
                        "phy:1"
                    ],
                    "type": "merge"
                }
            ],
            "core_mask": "0xfc02",
            "num_vhost": 2,
            "pci_address": "00:05.0",
            "physical_network": "phys2"
        }
    ]
  }

/spp/openstack/vhost/<host>/<phys>/<vhost_id>
+++++++++++++++++++++++++++++++++++++++++++++

Indicates usage of each vhost. It is "None" if it is not used, or "port id" if it is used.

/spp/openstack/port_status/<host>/<port id>
+++++++++++++++++++++++++++++++++++++++++++

Used to notify the spp-agent to the spp mechanism driver that the plug process
is completed. When the plug process is done, the value "up" is written.

/spp/openstack/bind_port/<host>/<port id>
+++++++++++++++++++++++++++++++++++++++++

A dict that stores information on the port to be plugged.
The key and value of dict are as follows.

vhost_id
  Id of vhost connected to the port.

mac_address
  mac address of the port.

vlan_id
  vlan id of the network to which the port belongs. (It exists only when using vlan network)

/spp/openstack/action/<host>/<port id>
++++++++++++++++++++++++++++++++++++++

Used to request plug/unplug the port from spp mechanism driver to spp-agent.
Values are "plug" when requesting plug, "unplug" when requesting unplug.

Tips: How to check etcd key
---------------------------

You can confirm with etcdctl command on the control node. devstack builds
etcd3 itself, you need to use files/etcd-v3.1.7-linux-amd64/etcdctl under
devstack directory. Also, you need to use etcd V3 API.

example(just after construction)::

  $ ETCDCTL_API=3 ~/devstack/files/etcd-v3.1.7-linux-amd64/etcdctl --endpoints 192.168.122.80:2379 get --prefix /spp
  /spp/openstack/configuration/spp4
  {"vf": [{"num_vhost": 2, "physical_network": "phys1", ...snipped...}, {"num_vhost": 2, "physical_network": "phys2", ...snipped...}]}
  /spp/openstack/vhost/spp4/phys1/0
  None
  /spp/openstack/vhost/spp4/phys1/1
  None
  /spp/openstack/vhost/spp4/phys2/2
  None
  /spp/openstack/vhost/spp4/phys2/3
  None

example(one vhostuser using)::

  $ ETCDCTL_API=3 ~/devstack/files/etcd-v3.1.7-linux-amd64/etcdctl --endpoints 192.168.122.80:2379 get --prefix /spp
  /spp/openstack/action/spp4/6160c9da-b2d5-4236-8413-7d646e5c0ae2
  plug
  /spp/openstack/bind_port/spp4/6160c9da-b2d5-4236-8413-7d646e5c0ae2
  {"vhost_id": 0, "mac_address": "fa:16:3e:a0:da:db"}
  /spp/openstack/configuration/spp4
  {"vf": [{"num_vhost": 2, "physical_network": "phys1", ...snipped...}, {"num_vhost": 2, "physical_network": "phys2", ...snipped...}]}
  /spp/openstack/port_status/spp4/6160c9da-b2d5-4236-8413-7d646e5c0ae2
  up
  /spp/openstack/vhost/spp4/phys1/0
  6160c9da-b2d5-4236-8413-7d646e5c0ae2
  /spp/openstack/vhost/spp4/phys1/1
  None
  /spp/openstack/vhost/spp4/phys2/2
  None
  /spp/openstack/vhost/spp4/phys2/3
  None
