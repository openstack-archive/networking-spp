======================
Using tap-as-a-service
======================

Tap as a service (taas) is available in networking-spp.
For details of taas, see https://github.com/openstack/tap-as-a-service.

Installation
============

local.conf
----------

In order to use taas, it is necessary to add some lines to local.conf.
The example shown below is based on the example described in the
:doc:`installation` and lines for taas are added. Lines with comment
are added for taas.

Control node::

  [[local|localrc]]

  Q_AGENT=linuxbridge

  enable_plugin networking-spp https://github.com/openstack/networking-spp master

  SPP_MODE=controller

  enable_service etcd3

  enable_plugin tap-as-a-service https://github.com/openstack/tap-as-a-service           # these three lines must be added for taas.
  enable_service taas                                                                    #
  TAAS_SERVICE_DRIVER=TAAS:SPP:networking_spp.service_drivers.taas.SppTaasDriver:default #

  [[post-config|/$Q_PLUGIN_CONF_FILE]]
  [ml2]
  type_drivers=vxlan,flat,vlan
  mechanism_drivers=linuxbridge,spp

  [ml2_type_flat]
  flat_networks=phys1

  [ml2_type_vlan]
  network_vlan_ranges=phys2:400:499

  [agent]
  extensions=     # this line is necessary for the linuxbridge agent not to use taas.
                  # it is OK to specify services other than taas used by the linuxbridge agent.

Compute node::

  [[local|localrc]]

  Q_AGENT=linuxbridge

  enable_plugin networking-spp https://github.com/openstack/networking-spp master

  SPP_PRIMARY_SOCKET_MEM=1024,1024
  SPP_PRIMARY_CORE_MASK=0x2
  DPDK_PORT_MAPPINGS=00:04.0#phys1#2#0xfe,00:05.0#phys2#2#0xfc02

  SPP_MIRROR=2#0x30002    # specify the mirror configuration.

  disable_all_services
  enable_service n-cpu
  enable_service q-agt
  enable_service q-spp-agt

  [[post-config|$NOVA_CONF]]
  [DEFAULT]
  vcpu_pin_set = 8,9,18,19

  [libvirt]
  cpu_mode = host-passthrough


SPP_MIRROR
++++++++++

Specify mirror configuration for taas.
This must be specified if taas is used on the compute node.

The format is as follows::

  <number of mirror components>#<core_mask>

number of mirror components
  number of mirror components to be allocated on the spp_mirror process.
  note that one component is consumed for one direction of a tap-flow.
  (ex. if direction of a tap-flow is 'BOTH', two components are consumed.)

core_mask
  core_mask of the spp_mirror process.

example::

  SPP_MIRROR=2#30002

Note about non default components configuration
-----------------------------------------------

If you use non default components configuration (i.e. ``SPP_COMPONENT_CONF``
parameter specified), it is necessary to add mirror configuration
to the yaml file as well.

top level parameters
++++++++++++++++++++

+---------+---------------------------------+
| key     | value                           |
+=========+=================================+
| mirror  | array of mirror component info  |
+---------+---------------------------------+

mirror component info
+++++++++++++++++++++

+---------+---------------------------------------------------------------------+
| key     | value                                                               |
+=========+=====================================================================+
| core    | core id                                                             |
+---------+---------------------------------------------------------------------+
| ports   | array of ports used by the component. two rings must be specified.  |
+---------+---------------------------------------------------------------------+

yaml example::

  vf:
  <...snip>

  mirror:
  - core: 16
    ports: ['ring:9', 'ring:10']
  - core: 17
    ports: ['ring:11', 'ring:12']

Warning
+++++++

When taas is used, it must be configured so that vhost and forward
components are connected. (i.e. configuration such as
:ref:`resource-saving-example-2` is not permitted if taas is used.)

Usage
=====

Restriction
-----------

The service port and the source port must be on the same host
although these need not be the same network.

CLI example
-----------

openstack CLI is not yet supported for taas, so use neutron CLI.

creating tap-service::

  neutron tap-service-create --name ts1 --port 376d6cf2-300b-4dde-88e4-e160db6ec56d

creating tap-flow::

  neutron tap-flow-create --name tf1 --port 242eeca9-ff69-4ed5-a305-5582ebe18c93

deleting tap-flow::

  neutron tap-flow-delete tf1

deleting tap-service::

  neutron tap-service-delete ts1

Warning
-------

The setting of taas on the host is set when tap-flow is created, and
is canceled when tap-flow is deleted.
When the service port or the source port is deleted (usually when
the VM is deleted), the taas setting on the host is canceled too,
but since the tap resources remain, it is necessary to explicitly
delete these. Normally the tap resources should be deleted before
deleting VMs.

Architecture
============

Processes on compute node
-------------------------

A spp_mirror process is added.

spp_mirror
  It is a DPDK secondary process provided by SPP.
  It offers mirror components.


Component composition when using taas
-------------------------------------

IN direction::

            +-----------+
  [ring]--rx|   merge   |tx--[vhost] service port
            +-----------+
                rx
                 |                       spp_vf
  ---------------+---------------------------------
                 |
               [ring]
                 |
                tx
             +-----------+
         +-rx|  mirror   |               spp_mirror
         |   +-----------+
         |      tx
         |       |
         |     [ring]
         |       |
  -------+-------+---------------------------------
         |       |                       spp_vf
         |       |    +----------+
  [ring]-+       +--rx| forward  |tx--[vhost] source port
                      +----------+

OUT direction::

            +-----------+
  [ring]--rx|   merge   |tx--[vhost] service port
            +-----------+
                rx
                 |                       spp_vf
  ---------------+---------------------------------
                 |
               [ring]
                 |
                tx
             +-----------+
             |  mirror   |rx-+           spp_mirror
             +-----------+   |
                tx           |
                 |           |
               [ring]        |
                 |           |
  ---------------+-----------+---------------------
                 |           |           spp_vf
  +---------+    |           |            +----------+
  | merge   |rx--+           +--[ring]--tx| forward  |rx--[vhost] source port
  +---------+                             +----------+

Note
++++

* vhost for service port is connected to merge component in the above figures.
  It is forward component usually, but spp-agent replaces it to merge component
  if taas is used.
* spp_vf the service port belongs to and spp_vf the source port belongs to
  may be same. It is divided for simplicity in the above figures.
* IN and OUT can be set simultaneously for one source port. Figures are
  separated for simplicity.


etcd keys
---------

The following are keys added or modified for taas.

==============================================  ======== ===============  =========
key                                             devstack spp mech driver  spp-agent
==============================================  ======== ===============  =========
/spp/openstack/configuration/<host>               C        R                R
/spp/openstack/mirror/<host>/<mirror id>          C        RW               W
/spp/openstack/tap_status/<host>/<tap flow id>             R                CWD
/spp/openstack/tap_info/<host>/<tap flow id>               CW               RD
/spp/openstack/tap_action/<host>/<tap flow id>             CW               RD
==============================================  ======== ===============  =========

/spp/openstack/configuration/<host>
+++++++++++++++++++++++++++++++++++

mirror info is added in addition to vf info.

mirror
  array of mirror component info

mirror component info is as follows.

core
  core id

ports
  array of ports used by the component

example(It is shaping for ease of viewing)::

  {
    "vf": [...snip],
    "mirror": [
        {
            "core": 16,
            "ports": ["ring:8", "ring:9"]
        },
        {
            "core": 17,
            "ports": ["ring:10", "ring:11"]
        }
  }

/spp/openstack/mirror/<host>/<mirror id>
++++++++++++++++++++++++++++++++++++++++

Indicates usage of each mirror component.
It is "None" if it is not used, or "tap flow id" if it is used.

/spp/openstack/tap_status/<host>/<tap flow id>
++++++++++++++++++++++++++++++++++++++++++++++

Used to notify the spp-agent to the spp mechanism driver that
the tap-flow setting process is completed. When the tap-flow setting
process is done, the value "up" is written.

/spp/openstack/tap_info/<host>/<tap flow id>
++++++++++++++++++++++++++++++++++++++++++++

A dict that stores tap-flow information to be set.
The key and value of dict are as follows.

service_port
  port id of the service port.

source_port
  port id of the source port.

mirror_in
  mirror id used for IN tap. it is set if tap direction is IN or BOTH, otherwise None.

mirror_out
  mirror id used for OUT tap. it is set if tap direction is OUT or BOTH, otherwise None.

/spp/openstack/tap_action/<host>/<tap flow id>
++++++++++++++++++++++++++++++++++++++++++++++

Used to request set/unset the tap-flow from spp mechanism driver to spp-agent.
Values are "plug" when requesting tap-flow set, "unplug" when requesting
tap-flow unset.
