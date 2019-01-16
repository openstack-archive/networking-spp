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

import requests

from oslo_log import log as logging


LOG = logging.getLogger(__name__)


class SppVfApiCommon(object):

    def __init__(self, sec_id, api_ip_addr, api_port, proc_type):
        self.sec_id = sec_id
        self.api_port = api_port
        self.host_url = "http://%s:%d" % (api_ip_addr, api_port)
        self.proc_url = "/v1/%ss/%d" % (proc_type, sec_id)
        self.info = None

    def send_request(self, method, url, data=None):
        path = self.host_url + self.proc_url + url
        r = requests.request(method, path, json=data)
        if r.status_code >= 400:
            raise RuntimeError("%s %s error: %s" %
                               (method, self.proc_url + url, r.text))
        if r.status_code != 204:
            return r.json()

    def get_status(self):
        ret = self.send_request("GET", "")
        LOG.info("info %d: %s", self.sec_id, ret)
        self.info = ret

    def make_component(self, comp_name, core_id, comp_type):
        data = {"name": comp_name, "core": core_id, "type": comp_type}
        self.send_request("POST", "/components", data)

    def port_add(self, port, direction, comp_name, op=None, vlan_id=None):
        data = {"action": "attach", "port": port, "dir": direction}
        if op:
            if op == "add_vlantag":
                vlan = {"operation": "add", "id": vlan_id, "pcp": 0}
            else:
                vlan = {"operation": "del"}
            data["vlan"] = vlan
        path = "/components/%s/ports" % comp_name
        self.send_request("PUT", path, data)

    def port_del(self, port, direction, comp_name):
        data = {"action": "detach", "port": port, "dir": direction}
        path = "/components/%s/ports" % comp_name
        self.send_request("PUT", path, data)

    def port_exist(self, port, direction, comp_name):
        for comp in self.info["components"]:
            if comp["name"] == comp_name:
                ports = (comp["rx_port"] if direction == "rx"
                         else comp["tx_port"])
                for p in ports:
                    if port == p["port"]:
                        return True
        return False


class SppVfApi(SppVfApiCommon):

    def __init__(self, sec_id, api_ip_addr, api_port):
        super(SppVfApi, self).__init__(sec_id, api_ip_addr, api_port, "vf")

    def set_classifier_table(self, mac_address, port):
        data = {"action": "add", "type": "mac", "mac_address": mac_address,
                "port": port}
        self.send_request("PUT", "/classifier_table", data)

    def clear_classifier_table(self, mac_address, port):
        data = {"action": "del", "type": "mac", "mac_address": mac_address,
                "port": port}
        self.send_request("PUT", "/classifier_table", data)

    def set_classifier_table_with_vlan(self, mac_address, port, vlan_id):
        data = {"action": "add", "type": "vlan", "mac_address": mac_address,
                "port": port, "vlan": vlan_id}
        self.send_request("PUT", "/classifier_table", data)

    def clear_classifier_table_with_vlan(self, mac_address, port, vlan_id):
        data = {"action": "del", "type": "vlan", "mac_address": mac_address,
                "port": port, "vlan": vlan_id}
        self.send_request("PUT", "/classifier_table", data)


class SppMirrorApi(SppVfApiCommon):

    def __init__(self, sec_id, api_ip_addr, api_port):
        super(SppMirrorApi, self).__init__(sec_id, api_ip_addr, api_port,
                                           "mirror")

    def make_component(self, comp_name, core_id):
        super(SppMirrorApi, self).make_component(comp_name, core_id,
                                                 "mirror")
