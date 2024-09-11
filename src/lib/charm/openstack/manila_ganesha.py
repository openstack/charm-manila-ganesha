# Copyright 2019 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import collections
import errno
import os
import socket
import subprocess

import charms_openstack.charm
import charms_openstack.adapters
import charms_openstack.plugins
import charms_openstack.charm.utils
import charmhelpers.contrib.network.ip as ch_net_ip
import charms.reactive.relations as relations
from charmhelpers.core.host import (
    cmp_pkgrevno,
    service_pause,
    mkdir,
    path_hash,
    write_file,
)
from charmhelpers.core.hookenv import (
    ERROR,
    config,
    goal_state,
    local_unit,
    log,
    network_get,
)
from charmhelpers.contrib.hahelpers.cluster import (
    is_clustered,
    peer_units,
)
from charmhelpers.contrib.storage.linux.ceph import (
    CephBrokerRq,
)
import charmhelpers.core as ch_core


MANILA_DIR = '/etc/manila/'
MANILA_CONF = MANILA_DIR + "manila.conf"
MANILA_SSL_DIR = MANILA_DIR + "ssl/"
MANILA_CLIENT_CERT_FILE = MANILA_SSL_DIR + "cert.crt"
MANILA_CLIENT_KEY_FILE = MANILA_SSL_DIR + "cert.key"
MANILA_CLIENT_CA_FILE = MANILA_SSL_DIR + "ca.crt"
MANILA_LOGGING_CONF = MANILA_DIR + "logging.conf"
MANILA_API_PASTE_CONF = MANILA_DIR + "api-paste.ini"
CEPH_CONF = '/etc/ceph/ceph.conf'
GANESHA_CONF = '/etc/ganesha/ganesha.conf'

CEPH_CAPABILITIES = [
    "mds", "allow *",
    "mgr", "allow *",
    "osd", "allow rw",
    "mon", "allow r, "
    "allow command \"auth del\", "
    "allow command \"auth caps\", "
    "allow command \"auth get\", "
    "allow command \"auth get-or-create\""]

# include/crm/common/results.h crm_exit_e enum specifies
# OS-independent status codes.
CRM_EX_ERROR = 1
CRM_EX_NOSUCH = 105

CRM_ERR_MSG = 'Unexpected crm return code: {} {}'


@charms_openstack.adapters.config_property
def access_ip(config):
    """Return the list of lines from the backends that need to go into the
    various configuration files.

    This one is for manila.conf
    :returns list of lines: the config for the manila.conf file
    """
    return config.charm_instance.access_ip


@charms_openstack.adapters.config_property
def recovery_backend(config):
    return config.charm_instance.recovery_backend


@charms_openstack.adapters.config_property
def local_ip(_config):
    return ch_net_ip.get_relation_ip('tenant-storage')


@charms_openstack.adapters.config_property
def use_memcache(config):
    """Do not enable memcache."""
    return False


class KeystoneCredentialAdapter(
        charms_openstack.adapters.OpenStackRelationAdapter):
    """Modifies the keystone-credentials interface to act like keystone."""

    def __init__(self, relation):
        super(KeystoneCredentialAdapter, self).__init__(relation)
        self.service_domain
        self.service_domain_id
        self.service_host
        self.service_password
        self.service_port
        self.service_protocol
        self.service_tenant
        self.service_tenant_id
        self.service_username

    @property
    def service_domain(self):
        return self.credentials_user_domain_name

    @property
    def service_domain_id(self):
        return self.credentials_user_domain_id

    @property
    def service_host(self):
        return self.credentials_host

    @property
    def service_password(self):
        return self.credentials_password

    @property
    def service_port(self):
        return self.credentials_port

    @property
    def service_protocol(self):
        return self.credentials_protocol

    @property
    def service_tenant(self):
        return self.credentials_project

    @property
    def service_tenant_id(self):
        return self.credentials_project_id

    @property
    def service_username(self):
        return self.credentials_username


class TlsCertificatesAdapter(
        charms_openstack.adapters.OpenStackRelationAdapter):
    """Modifies the keystone-credentials interface to act like keystone."""

    def _resolve_file_name(self, path):
        if os.path.exists(path):
            return path
        return None

    @property
    def certfile(self):
        return self._resolve_file_name(MANILA_CLIENT_CERT_FILE)

    @property
    def keyfile(self):
        return self._resolve_file_name(MANILA_CLIENT_KEY_FILE)

    @property
    def cafile(self):
        return self._resolve_file_name(MANILA_CLIENT_CA_FILE)


class GaneshaCharmRelationAdapters(
        charms_openstack.adapters.OpenStackRelationAdapters):
    relation_adapters = {
        'amqp': charms_openstack.adapters.RabbitMQRelationAdapter,
        'ceph': charms_openstack.plugins.CephRelationAdapter,
        'manila-ganesha': charms_openstack.adapters.OpenStackRelationAdapter,
        'identity-service': KeystoneCredentialAdapter,
        'shared_db': charms_openstack.adapters.DatabaseRelationAdapter,
        'certificates': TlsCertificatesAdapter,
    }


class ManilaGaneshaCharm(charms_openstack.charm.HAOpenStackCharm,
                         charms_openstack.plugins.BaseOpenStackCephCharm,
                         ):
    release = 'rocky'
    name = 'ganesha'
    python_version = 3
    source_config_key = 'openstack-origin'
    packages = [
        'ceph-common',
        'python3-cephfs',
        'python3-rados',
        'nfs-ganesha-ceph',
        'manila-share',
        'python3-manila',
    ]
    required_relations = [
        'amqp',
        'ceph',
        'identity-service',
        'shared-db',
    ]
    user = group = 'manila'

    adapters_class = GaneshaCharmRelationAdapters
    # ceph_key_per_unit_name = True

    # Note(coreycb): The pause, resume, and restart-services actions for
    # manila-ganesha will do nothing until the services in the following list
    # are enabled. The reason they are currently not enabled is because
    # os_utils.manage_payload_services() restarts systemd services which will
    # result in multiple manila-ganesha peer units with running services.
    # We need to override starts/restarts similar to how we override
    # service_restart and service_start below. For now, the hacluster pause
    # action can be used. It will disable manila-share and nfs-ganesha services
    # locally and run them on another unit. The hacluster resume action can
    # then be run to allow the services to once again be run locally if needed.
    # These services can be enabled once the following are overriden from
    # class OpenStackCharm:
    #   run_pause_or_resume()
    #   enable_services()
    #   disable_services()
    #   restart_services()
    services = [
        # 'nfs-ganesha',
        # 'manila-share',
    ]
    ha_resources = ['vips', 'dnsha']
    version_package = release_pkg = 'manila-common'

    package_codenames = {
        'manila-common': collections.OrderedDict([
            ('7', 'rocky'),
            ('8', 'stein'),
            ('9', 'train'),
            ('10', 'ussuri'),
            ('11', 'victoria'),
            ('12', 'wallaby'),
            ('13', 'xena'),
            ('14', 'yoga'),
            ('15', 'zed'),
            ('16', 'antelope'),
            ('17', 'bobcat'),
            ('18', 'caracal'),
        ]),
    }

    @property
    def restart_map(self):
        return {
            GANESHA_CONF: ['nfs-ganesha'],
            MANILA_CONF: ['manila-share', 'nfs-ganesha'],
            MANILA_API_PASTE_CONF: ['manila-share', 'nfs-ganesha'],
            MANILA_LOGGING_CONF: ['manila-share', 'nfs-ganesha'],
            CEPH_CONF: ['manila-share', 'nfs-ganesha'],
        }

    @property
    def service_to_resource_map(self):
        # TODO: interface-hacluster should be extended to provide
        # a resource name based on a service name instead or a
        # capability to lookup SystemdService objects containing the
        # resource name as a property. This map is only valid due to
        # how the code of this charm calls add_systemd_service.
        return {
            'manila-share': 'res_manila_share_manila_share',
            'nfs-ganesha': 'res_nfs_ganesha_nfs_ganesha'
        }

    @staticmethod
    def _crm_no_such_resource_code():
        return (errno.ENXIO if cmp_pkgrevno('pacemaker', '2.0.0') < 0
                else CRM_EX_NOSUCH)

    def install(self):
        """Install packages related to this charm based on
        contents of self.packages attribute, after first
        configuring the installation source.
        """
        # Use goal-state to determine if we are expecting multiple units
        # and, if so, mask the manila-share service so that it only ever
        # gets run by pacemaker.
        _goal_state = goal_state()
        peers = (key for key in _goal_state['units']
                 if '/' in key and key != local_unit())
        if len(list(peers)) > 0:
            service_pause('manila-share')
        super().install()

    def service_restart(self, service_name):
        res_name = self.service_to_resource_map.get(service_name, None)
        if not res_name or not peer_units():
            super().service_restart(service_name)
            return
        # crm_resource does not have a --force-restart command to do a
        # local restart, however, --node can be specified to limit the
        # scope of a restart operation to the local node. The node name
        # is the hostname present in the UTS namespace unless higher
        # precedence overrides are specified in corosync.conf.
        try:
            subprocess.run(
                ['crm_resource', '--wait', '--resource', res_name,
                 '--restart', '--node', socket.gethostname()],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
            )
        except subprocess.CalledProcessError as e:
            if e.returncode == self._crm_no_such_resource_code():
                err_msg = e.stderr.decode('utf-8')
                if 'not found' in err_msg or 'is not running on' in err_msg:
                    # crm_resource --restart returns CRM_EX_NOSUCH when a
                    # resource is not running on the specified --node. Assume
                    # it is running somewhere else in the cluster and that its
                    # lifetime is managed by Pacemaker (i.e. don't attempt to
                    # forcefully start it locally).
                    return
                else:
                    raise RuntimeError(CRM_ERR_MSG.format(e.returncode,
                                                          err_msg)) from e
            else:
                raise RuntimeError(CRM_ERR_MSG.format(e.returncode,
                                                      '')) from e

    def service_start(self, service_name):
        res_name = self.service_to_resource_map.get(service_name, None)
        if not res_name or not peer_units():
            super().service_start(service_name)
            return
        # Start a resource locally which will cause Pacemaker to start the
        # respective service. 'crm resource start' will not start the service
        # if the resource should not be running on this unit.
        try:
            subprocess.run(
                ['crm', '--wait', 'resource', 'start', res_name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
            )
        except subprocess.CalledProcessError as e:
            if e.returncode == CRM_EX_ERROR:
                err_msg = e.stderr.decode('utf-8')
                if 'not found' in err_msg:
                    return
                else:
                    raise RuntimeError(CRM_ERR_MSG.format(e.returncode,
                                                          err_msg)) from e
            else:
                raise RuntimeError(CRM_ERR_MSG.format(e.returncode,
                                                      '')) from e

    def service_stop(self, service_name):
        res_name = self.service_to_resource_map.get(service_name, None)
        if not res_name or not peer_units():
            super().service_stop(service_name)
            return
        # Stop a resource locally which will cause Pacemaker to start the
        # respective service (force-start operates locally).
        try:
            subprocess.run(
                ['crm_resource', '--wait', '--resource', res_name,
                 '--force-stop'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
            )
        except subprocess.CalledProcessError as e:
            if e.returncode == self._crm_no_such_resource_code():
                err_msg = e.stderr.decode('utf-8')
                if 'not found' in err_msg:
                    # Fallback to starting the service itself since:
                    # 1. It could be that the resource hasn't been defined yet;
                    # 2. This is a single-unit deployment without hacluster.
                    super().service_stop(service_name)
                else:
                    raise RuntimeError(CRM_ERR_MSG.format(e.returncode,
                                                          err_msg)) from e
            else:
                raise RuntimeError(CRM_ERR_MSG.format(e.returncode,
                                                      '')) from e

    @property
    def access_ip(self):
        vips = config().get('vip')
        if vips:
            vips = vips.split()
        clustered = is_clustered()
        net_addr = ch_net_ip.get_relation_ip('tenant-storage')
        bound_cidr = ch_net_ip.resolve_network_cidr(
            ch_net_ip.network_get_primary_address('tenant-storage')
        )
        if clustered and vips:
            for vip in vips:
                if ch_net_ip.is_address_in_network(bound_cidr, vip):
                    return vip
        return net_addr

    @property
    def recovery_backend(self):
        return 'fs'

    def enable_memcache(self, *args, **kwargs):
        return False

    def get_amqp_credentials(self):
        """Provide the default amqp username and vhost as a tuple.

        :returns (username, host): two strings to send to the amqp provider.
        """
        return (self.options.rabbit_user, self.options.rabbit_vhost)

    def get_database_setup(self):
        """Provide the default database credentials as a list of 3-tuples

        returns a structure of:
        [
            {'database': <database>,
             'username': <username>,
             'hostname': <hostname of this unit>
             'prefix': <the optional prefix for the database>, },
        ]

        :returns [{'database': ...}, ...]: credentials for multiple databases
        """
        return [
            dict(
                database=self.options.database,
                username=self.options.database_user, )
        ]

    def request_ceph_permissions(self, ceph):
        rq = ceph.get_current_request() or CephBrokerRq()
        log("Requesting ceph permissions for client: {}".format(
            ch_core.hookenv.application_name()), level=ch_core.hookenv.INFO)
        rq.add_op({'op': 'set-key-permissions',
                   'permissions': CEPH_CAPABILITIES,
                   'client': ch_core.hookenv.application_name()})
        ceph.send_request_if_needed(rq)

    def get_client_cert_cn_sans(self):
        """Get the tuple (cn, [sans]) for a client certificiate.

        This is for the keystone endpoint/interface, so generate the client
        cert data for that.
        """
        try:
            ingress = network_get('identity-service')['ingress-addresses']
        except Exception as e:
            # if it didn't work, log it as an error, and return (None, None)
            log(f"Getting ingress for identity-service failed: {str(e)}",
                level=ERROR)
            return (None, None)
        return (ingress[0], ingress[1:])

    def handle_changed_client_cert_files(self, ca, cert, key):
        """Handle changes to client cert, key or ca.

        If the client certs have changed on disk, rerender and restart manila.

        The cert and key need to be written to:

        - /etc/manila/ssl/cert.crt - MANILA_CLIENT_CERT_FILE
        - /etc/manila/ssl/cert.key - MANILA_CLIENT_KEY_FILE
        - /etc/manila/ssl/ca.cert  - MANILA_CLIENT_CA_FILE
        """
        # lives ensrure that the cert dir exists
        mkdir(MANILA_SSL_DIR)
        paths = {
            MANILA_CLIENT_CA_FILE: ca,
            MANILA_CLIENT_CERT_FILE: cert,
            MANILA_CLIENT_KEY_FILE: key,
        }
        checksums = {path: path_hash(path) for path in paths.keys()}
        # write or remove the files.
        for path, contents in paths.items():
            if contents is None:
                # delete the file
                realpath = os.path.abspath(path)
                path_exists = os.path.exists(realpath)
                if path_exists:
                    try:
                        os.remove(path)
                    except OSError as e:
                        log("Path {} couldn't be deleted: {}"
                            .format(path, str(e)), level=ERROR)
            else:
                write_file(path,
                           contents.encode(),
                           owner=self.user,
                           group=self.group,
                           perms=0o640)
        new_checksums = {path: path_hash(path) for path in paths.keys()}
        if new_checksums != checksums:
            interfaces = (
                'ceph.available',
                'amqp.available',
                'manila-plugin.available',
                'shared-db.available',
                'identity-service.available',
                'certificates.available',
            )
            # check all the interfaces are available
            endpoints = []
            for interface in interfaces:
                endpoint = relations.endpoint_from_flag(interface)
                if not endpoint:
                    # if not available don't attempt to render
                    return
                endpoints.append(endpoint)
            self.render_with_interfaces(endpoints)


class ManilaGaneshaUssuriCharm(ManilaGaneshaCharm,
                               ):
    release = 'ussuri'

    @property
    def recovery_backend(self):
        return 'rados_ng'
