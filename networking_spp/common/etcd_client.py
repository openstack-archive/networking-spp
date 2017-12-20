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

import etcd3gw


class EtcdClient(object):
    """Define etcd client.

    Only define methods used for networking-spp and make return
    value simple.
    It maybe used 'etcd3' instead of 'etcd3gw' in the future.
    This class also intends to hide incompatibility between
    etcd3 and etcd3gw (when etcd3 will be used).
    """

    def __init__(self, host, port):
        self.client = etcd3gw.client(host, port)

    def get(self, key):
        data = self.client.get(key)
        if data:
            return data[0]

    def get_prefix(self, prefix):
        data = self.client.get_prefix(prefix)
        if data:
            return [(meta['key'], value) for value, meta in data]
        return []

    def put(self, key, value):
        self.client.put(key, value)

    def replace(self, key, old_value, new_value):
        return self.client.replace(key, old_value, new_value)

    def delete(self, key):
        return self.client.delete(key)

    def watch_prefix(self, prefix):
        # workaround for etcd3gw bug
        kwargs = {}
        kwargs['range_end'] = \
            etcd3gw.utils._increment_last_byte(prefix)
        orig_iter, cancel = self.client.watch(prefix, **kwargs)

        def iterator():
            for event in orig_iter:
                yield (event['kv']['key'], event['kv'].get('value'))

        return iterator()

    def watch_once(self, key, timeout=None):
        try:
            event = self.client.watch_once(key, timeout=timeout)
            return (event['kv']['key'], event['kv'].get('value'))
        except Exception:
            return (None, None)
