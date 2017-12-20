# Copyright 2017 NTT
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import etcd3
import sys

SPP_ROOT = "/spp/openstack/"


def config_path(host):
    return SPP_ROOT + "configuration/" + host


def vhost_path(host):
    return SPP_ROOT + "vhost/%s" % host


def bind_port_path(host):
    return SPP_ROOT + "bind_port/%s" % host


def action_path(host):
    return SPP_ROOT + "action/%s" % host


def port_status_path(host):
    return SPP_ROOT + "port_status/%s" % host


def main():
    if len(sys.argv) < 4:
        print("usage: spp-config-destroy host etcd_host etcd_port")
        return 1
    host = sys.argv[1]
    etcd_host = sys.argv[2]
    etcd_port = sys.argv[3]

    etcd = etcd3.client(etcd_host, etcd_port)
    etcd.delete(config_path(host))
    etcd.delete_prefix(vhost_path(host))
    etcd.delete_prefix(bind_port_path(host))
    etcd.delete_prefix(action_path(host))
    etcd.delete_prefix(port_status_path(host))


if __name__ == "__main__":
    sys.exit(main())
