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

spp-agent
  It communicates with spp_primary and spp_vf processes and
  set SPP according to the request from neutron-server.
  The 'spp' script which controls spp_primary and spp_vf is provided
  by SPP. But in the OpenStack environment spp-agent is used to
  control spp processes instead of the 'spp' script.

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
  |          | |       | |              | |                       spp-agent      |
  |  spp_vf  | v       | v      spp_vf  | v                     +-----------+    |
  |     +---------------------+    +---------------------+      |           |    |
  |     | +-------+ +-------+ |    | +-------+ +-------+ |      +-----------+    |
  |     | |vhost:0| |vhost:1| |    | |vhost:2| |vhost:3| |                       |
  |     | +-------+ +-------+ |    | +-------+ +-------+ |                       |
  |     |                     |    |                     |                       |
  |     |   classifier/merge  |    |   classifier/merge  |                       |
  |     +---------------------+    +---------------------+                       |
  |              ^  |                       ^  |                                 |
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

Configration example
++++++++++++++++++++

* Both spp_primary and spp_vfs share the master core and use core id 1.
* spp_vf(1) uses two vhostusers and uses core id 2 to 7.
* spp_vf(2) uses two vhostusers and uses core id 10 to 15.

::

  SPP_PRIMARY_CORE_MASK=0x2
  DPDK_PORT_MAPPINGS=00:04.0#phys1#2#0xfe,00:05.0#phys2#2#xfc02

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

pci_address
  PCI address of the NIC

physical_network
  physical_network assigned to the NIC

num_vhost
  the number of vhostusers allocated for the NIC

core_mask
  core_mask of spp_vf for the NIC

example::

  [{"num_vhost": 2, "pci_address": "00:04.0", "physical_network": "phys1", "core_mask": "0xfe"}, {"num_vhost": 2, "pci_address": "00:05.0", "physical_network": "phys2", "core_mask": "0xfc02"}]

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
  [{"num_vhost": 2, "core_mask": "0xfe", "pci_address": "00:04.0", "physical_network": "phys1"}, {"num_vhost": 2, "core_mask": "0xfc02", "pci_address": "00:05.0", "physical_network": "phys2"}]
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
  [{"num_vhost": 2, "core_mask": "0xfe", "pci_address": "00:04.0", "physical_network": "phys1"}, {"num_vhost": 2, "core_mask": "0xfc02", "pci_address": "00:05.0", "physical_network": "phys2"}]
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
