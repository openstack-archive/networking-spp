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

import errno
import json
import socket
import subprocess

import eventlet
from oslo_log import log as logging


LOG = logging.getLogger(__name__)

MSG_SIZE = 4096
CONNECTION_TIMEOUT = 180


class SppConnectionManager(object):

    def __init__(self, sec_ids, pri_sock_port, sec_sock_port):
        self.pri_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.pri_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.pri_sock.bind(('127.0.0.1', pri_sock_port))
        self.pri_sock.listen(1)

        self.pri_sem = eventlet.semaphore.Semaphore(value=0)
        self.pri_conn = None
        self.primary_listen_thread = eventlet.greenthread.spawn(
            self.accept_primary)

        self.sec_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sec_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sec_sock.bind(('127.0.0.1', sec_sock_port))
        self.sec_sock.listen(1)

        self.sec_sem = {}
        self.sec_conn = {}
        for sec_id in sec_ids:
            self.sec_sem[sec_id] = eventlet.semaphore.Semaphore(value=0)
            self.sec_conn[sec_id] = None
        self.secondary_listen_thread = eventlet.greenthread.spawn(
            self.accept_secondary)

    def accept_primary(self):
        while True:
            conn, _ = self.pri_sock.accept()
            if self.pri_conn is not None:
                LOG.warning("spp_primary reconnect !")
                with self.pri_sem:
                    try:
                        self.pri_conn.close()
                    except Exception:
                        pass
                    self.pri_conn = conn
                # NOTE: when spp_primary restart, all of spp_vfs must be
                # restarted. and then also spp-agent must be restarted.
                # these are out of controle of spp-agent.
            else:
                self.pri_conn = conn
                self.pri_sem.release()

    def accept_secondary(self):
        while True:
            conn, _ = self.sec_sock.accept()
            LOG.debug("sec accepted: get process id")
            conn.sendall("_get_client_id")
            data = conn.recv(MSG_SIZE)
            sec_id = self._get_process_id_from_response(data)
            if sec_id is None:
                LOG.error("get process id failed")
                continue
            elif sec_id not in self.sec_sem:
                LOG.error("Unknown secondary id: %d", sec_id)
            elif self.sec_conn[sec_id] is not None:
                LOG.warning("spp_vf(%d) reconnect !", sec_id)
                with self.sec_sem[sec_id]:
                    try:
                        self.sec_conn[sec_id].close()
                    except Exception:
                        pass
                    self.sec_conn[sec_id] = conn
                # NOTE: when spp_vf restart, spp-agent must be restarted.
                # this is out of controle of spp-agent.
            else:
                self.sec_conn[sec_id] = conn
                self.sec_sem[sec_id].release()

    def wait_connection(self, sec_id):
        with self.sec_sem[sec_id]:
            pass

    def wait_pri_connection(self):
        with self.pri_sem:
            pass

    def _cont_recv(self, conn):
        try:
            # must set non-blocking to recieve remining data not to happen
            # blocking here.
            # NOTE: MSG_DONTWAIT flag is not used since the flag does not work
            # under eventlet.
            conn.setblocking(False)
            data = ""
            while True:
                try:
                    rcv_data = conn.recv(MSG_SIZE)
                    data += rcv_data
                    if len(rcv_data) < MSG_SIZE:
                        break
                except socket.error as e:
                    if e.args[0] == errno.EAGAIN:
                        # OK, no data remining. this happens when recieve data
                        # length is just multiple of MSG_SIZE.
                        break
                    raise e
            return data
        finally:
            conn.setblocking(True)

    def sec_command(self, sec_id, command):
        with self.sec_sem[sec_id]:
            self.sec_conn[sec_id].sendall(command)
            data = self.sec_conn[sec_id].recv(MSG_SIZE)
            if data and len(data) == MSG_SIZE:
                # could not receive data at once. recieve remining data.
                data += self._cont_recv(self.sec_conn[sec_id])
            if data:
                LOG.debug("sec %d: %s: %s", sec_id, command, data)
                return data
            raise RuntimeError("sec %d: %s: no-data returned" %
                               (sec_id, command))

    def _get_process_id_from_response(self, response):
        try:
            ret = json.loads(response)
            result = ret["results"][0]["result"]
            if result != "success":
                return
            sec_id = ret["client_id"]
            LOG.debug("sec_id: %d", sec_id)
            return sec_id
        except Exception:
            pass


SPP_PRIMATY_SERVICE = "spp_primary.service"
SPP_VF_SERVICE = "spp_vf-{sec_id}.service"


def _is_service_active(service):
    args = ["systemctl", "is-active", service, "--quiet"]
    return subprocess.call(args) == 0


def _service_start(service):
    LOG.debug("start %s", service)
    args = ["sudo", "systemctl", "start", service]
    subprocess.call(args)


def _wait_service_initialized(func, *args):
    try:
        with eventlet.timeout.Timeout(CONNECTION_TIMEOUT):
            func(*args)
    except eventlet.timeout.Timeout:
        raise RuntimeError("Service initialization Timeout.")


def _start_primary(sec_ids, spp_cm):
    service = SPP_PRIMATY_SERVICE
    if _is_service_active(service):
        LOG.debug("%s already active.", service)
    else:
        for sec_id in sec_ids:
            if _is_service_active(SPP_VF_SERVICE.format(sec_id=sec_id)):
                LOG.info("spp_primary does not restart "
                         "because spp_vf is running.")
                return
        _service_start(service)
    _wait_service_initialized(spp_cm.wait_pri_connection)
    LOG.info("spp_primary executed.")


def ensure_spp_services_running(sec_ids, spp_cm):
    _start_primary(sec_ids, spp_cm)
    for sec_id in sec_ids:
        service = SPP_VF_SERVICE.format(sec_id=sec_id)
        if _is_service_active(service):
            LOG.debug("%s already active.", service)
        else:
            _service_start(service)
        _wait_service_initialized(spp_cm.wait_connection, sec_id)
        LOG.info("spp_vf(%d) executed.", sec_id)
