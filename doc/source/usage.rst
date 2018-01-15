========
Usage
========

Create an SPP network
=====================

example::

  $ openstack network create net1 --provider-network-type flat \
    --provider-physical-network phys1
  $ openstack subnet create sub1 --network net1 --no-dhcp --subnet-range 110.0.0.0/24

Setting of flavor
=================

You must launch a VM using huge page to use SPP networks.
In order to launch a VM using huge page, use a flavor with huge page property set.

Setting flavor example::

  $ openstack flavor set m1.large --property hw:mem_page_size=large

You can set the property to an existing flavor, or create a new flavor with it.

Note: Even if you use flavor without huge page property, it will succeed in
starting VM. However, vhostuser can not communicate.

Launch a VM
===========

* Use a flavor with huge page property set.
* Repeat network option for the number of virtual NICs.
  The VM operation network must be specify first.
* It is not possible to schedule depending on the usage status of vhostuser now,
  so you need to explicitly specify the execution host to start VM.
  It is done with --availability-zone option. (Note that it is possible only
  for admin users.)

example::

  $ openstack server create server1 --image ubuntu-dpdk --flavor m1.large \
    --network private --network net1 --availability-zone nova:host1

Add and remove port
===================

The port for SPP network can be added and removed after starting VM.

example to add::

  $ openstack port create p2 --network net2
  $ openstack server add port server1 p2

example to remove::

  $ openstack server remove port server1 p2
  $ openstack port delete p2
