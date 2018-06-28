# Copyright (c) 2017 NTT
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import netaddr


from neutron_tempest_plugin.common import ssh
from neutron_tempest_plugin import config
from neutron_tempest_plugin.scenario import base
from neutron_tempest_plugin.scenario import constants
from tempest.common import waiters
from tempest.lib.common.utils import data_utils
from tempest.lib import decorators

CONF = config.CONF


class SppTest(base.BaseTempestTestCase):
    credentials = ['primary', 'admin']
    force_tenant_isolation = False

    # Default to ipv4.
    _ip_version = 4

    @classmethod
    def setup_clients(cls):
        super(SppTest, cls).setup_clients()
        cls.client = cls.os_admin.network_client

    def _test_spp_connect(self, **net_kwargs):
        hypers = self.os_admin.hv_client.list_hypervisors()['hypervisors']
        azs = self.os_admin.az_client.list_availability_zones()
        az = str(azs['availabilityZoneInfo'][0]['zoneName'])
        h1 = az + ':' + str(hypers[0]['hypervisor_hostname'])
        h2 = az + ':' + str(hypers[1]['hypervisor_hostname'])

        network = self.create_network()
        subnet = self.create_subnet(network)

        network1 = self.create_network('network1', **net_kwargs)
        self.create_subnet(network1, reserve_cidr=False,
                           cidr=netaddr.IPNetwork('30.0.0.0/28'))

        secgroup = self.os_admin.network_client.create_security_group(
            name=data_utils.rand_name('secgroup'))
        self.security_groups.append(secgroup['security_group'])
        router = self.create_router_by_client()
        self.create_router_interface(router['id'], subnet['id'])
        clientk = self.os_admin.keypairs_client
        keypair = self.create_keypair(client=clientk)
        self.create_loginable_secgroup_rule(
            secgroup_id=secgroup['security_group']['id'],
            client=self.os_admin.network_client)

        server1 = self.create_server(
            flavor_ref=CONF.compute.flavor_ref,
            image_ref=CONF.compute.image_ref,
            key_name=keypair['name'],
            networks=[{'uuid': network['id']}, {'uuid': network1['id']}],
            security_groups=[{'name': secgroup['security_group']['name']}],
            availability_zone=h1
            )
        server2 = self.create_server(
            flavor_ref=CONF.compute.flavor_ref,
            image_ref=CONF.compute.image_ref,
            key_name=keypair['name'],
            networks=[{'uuid': network['id']}, {'uuid': network1['id']}],
            security_groups=[{'name': secgroup['security_group']['name']}],
            availability_zone=h2
            )

        waiters.wait_for_server_status(self.os_admin.servers_client,
                                       server1['server']['id'],
                                       constants.SERVER_STATUS_ACTIVE)
        waiters.wait_for_server_status(self.os_admin.servers_client,
                                       server2['server']['id'],
                                       constants.SERVER_STATUS_ACTIVE)

        port1 = self.client.list_ports(network_id=network['id'],
                                       device_id=server1[
                                       'server']['id'])['ports'][0]
        port2 = self.client.list_ports(network_id=network['id'],
                                       device_id=server2[
                                       'server']['id'])['ports'][0]

        clientp = self.os_admin.network_client
        fip1 = self.create_and_associate_floatingip(port1['id'],
                                                    client=clientp)

        fip2 = self.create_and_associate_floatingip(port2['id'],
                                                    client=clientp)

        # NOTE: initialization takes a long time after status becomes ACTIVE.
        ssh_client1 = ssh.Client(fip1['floating_ip_address'],
                                 CONF.validation.image_ssh_user,
                                 pkey=keypair['private_key'],
                                 timeout=400)

        ssh_client2 = ssh.Client(fip2['floating_ip_address'],
                                 CONF.validation.image_ssh_user,
                                 pkey=keypair['private_key'])

        ssh_client1.exec_command('dpdk_setup.sh')
        ssh_client2.exec_command('dpdk_setup.sh')

        ssh_client1.exec_command('sudo systemctl start dpdkapp_pong')

        cmd = 'sudo l2_ping_pong -- --ping | tail -n 1'
        res = ssh_client2.exec_command(cmd)
        print(res)

        self.assertTrue('Success.' in str(res))

    @decorators.idempotent_id('1361878f-c6b7-461f-9b24-0c3a8807f1e6')
    def test_spp_connect_flat(self):
        net_kwargs = {'provider:network_type': 'flat',
                      'provider:physical_network': 'phys1'}
        self._test_spp_connect(**net_kwargs)

    @decorators.idempotent_id('fe8471be-4d7b-4d74-9c67-8ba7a5e6859b')
    def test_spp_connect_vlan(self):
        net_kwargs = {'provider:network_type': 'vlan',
                      'provider:physical_network': 'phys2'}
        self._test_spp_connect(**net_kwargs)
