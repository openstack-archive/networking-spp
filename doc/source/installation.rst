============
Installation
============

It supports installation with devstack.

This document describes parts related to networking-spp. For the entire
devstack please refer to the devstack document_.

.. _document: https://docs.openstack.org/devstack/latest/

Control node
============

In control node, there are not many parameters related to networking-spp
that should be set in local.conf.

Parameters related to networking-spp are briefly described below with examples.
See devstack_ for details on parameters added by networking-spp.

.. _devstack: devstack.rst


Note that it is a fragment extracted only for networking-spp::

  [[local|localrc]]

  Q_AGENT=linuxbridge    # this must be specified for VM operation network. linuxbridge is an example.

  enable_plugin networking-spp https://github.com/openstack/networking-spp master  # this line must be specified.

  SPP_MODE=controller    # this line must be specified for control node.

  enable_service etcd3   # enable etcd3 since networking-spp uses etcd.

  [[post-config|/$Q_PLUGIN_CONF_FILE]]
  [ml2]
  type_drivers=vxlan,flat,vlan       # add 'flat' and 'vlan' if necessary, in addition to VM operation network (vxlan is an example).
  mechanism_drivers=linuxbridge,spp  # 'spp' must be added in addition to VM operation network (linuxbridge is an example).

  [ml2_type_flat]
  flat_networks=phys1                # specify physical networks for SPP flat type network. the value is an example.

  [ml2_type_vlan]
  network_vlan_ranges=phys2:400:499  # specify parameters for SPP vlan type network. the value is an example.

Compute node
============

In compute node, there are some tasks to do before executing devstack.

Preliminary design
------------------

Since SPP occupies memory and core, it must be designed beforehand for
its allocation amount. The amount of resources allocated to SPP and
the number of VMs that can be ran are limited by the host's memory and the
number of cores. In other words, it is necessaty to prepare enough memory
and cores to operate.

Allocation of hugepage
++++++++++++++++++++++

SPP uses hugepage and VMs that use SPP networks also need to use hugepage.
Normally, the memory on the host should be allocated as hugepage execpt
for the amount used by the system services.
The allocated hugepages are shared by SPP and VMs.

Distribution of core
++++++++++++++++++++

SPP needs to occupy some cores. It is necessary to separate the cores
for SPP so as not to be used from system services or VMs. Also, it is
better to separate the cores used by VMs from the cores used by system
services. Therefore, the cores on the host are classified into the
following three.

* For SPP
* For VMs
* other (for system services)

The number of cores occupied by SPP can be calculated by the following
formula.

"Number of physical NICs assigned to SPP" * 2 + "Total number of vhostusers" * 2

Preliminary Setting
-------------------

Set the following kernel boot parameters.

* hugepage related parameters
* isolcpus

(Note: The followng example is executed on ubuntu. Other distributios
may be different.)

Edit /etc/default/grub and add parameters to GRUB_CMDLINE_LINUX. For example::

  $ sudo vi /etc/default/grub
  ...
  # isolcpus specifies the cores excluding the cores for system services.
  GRUB_CMDLINE_LINUX="hugepagesz=2M hugepages=5120 isolcpus=2-19"
  # default_hugepagesz should be specified when using 1GB hugepage.
  #GRUB_CMDLINE_LINUX="default_hugepagesz=1G hugepagesz=1G hugepages=16 isolcpus=2-19"

Execute update-grub::

  $ sudo update-grub

Reboot the host::

  $ sudo reboot

The amount of allocated hugepages can be confirmed in /proc/meminfo. For example::

  $ cat /proc/meminfo
  ...
  HugePages_Total:      16
  HugePages_Free:       16
  HugePages_Rsvd:        0
  HugePages_Surp:        0
  Hugepagesize:    1048576 kB

Run devstack
------------

Note that it is necessary to execute devstack of compute node with control
node in operation.

Parameters related to networking-spp are briefly described below with examples.
See devstack_ for details on parameters added by networking-spp.

.. _devstack: devstack.rst

Note that it is a fragment extracted only for networking-spp::

  [[local|localrc]]

  Q_AGENT=linuxbridge       # this must be specified for VM operation network. linuxbridge is an example.

  enable_plugin networking-spp https://github.com/openstack/networking-spp master  # this line must be specified.

  SPP_PRIMARY_SOCKET_MEM=1024,1024                                       # amount of hugepage used by SPP. per numa node. MB.
  SPP_PRIMARY_CORE_MASK=0x2                                              # core mask used by spp_primary.
  DPDK_PORT_MAPPINGS=00:04.0#phys1#2#0xfe,00:05.0#phys2#2#0xfc02         # configuration information about NICs used for SPP.

  disable_all_services      # Normally, it is necessary and sufficient for the following three services.
  enable_service n-cpu      #
  enable_service q-agt      # agent for VM operation network.
  enable_service q-spp-agt  # spp-agent

  [[post-config|$NOVA_CONF]]
  [DFAULT]
  vcpu_pin_set = 8,9,16-19              # specify the cores for VMs.

  [libvirt]
  # This option enables VMs to use some features on host cpu, that are
  # needed for DPDK (e.g. SSE instruction).
  cpu_mode = host-passthrough

Post Work
---------

There are some tasks required after running devstack.

Suppression of apparmor
+++++++++++++++++++++++

Edit /etc/libvirt/qemu.conf and set security_driver to none::

  $ sudo vi /etc/libvirt/qemu.conf
  ...
  security_driver = "none"
  ...

Restart libvirtd::

  $ sudo systemctl restart libvirtd.service

Register compute node
+++++++++++++++++++++

This is the work done on the control node.

Execute nova-manage to register compute node::

  $ nova-manage cell_v2 discover_hosts

Note that it must be executed each time when a compute node is added.

It can be confirmed with the following command::

  $ openstack hypervisor list

Note: rebooting compute node
----------------------------

When rebooting compute node, you need to execute unstack.sh before shutting down
and execute stack.sh after rebooting.
