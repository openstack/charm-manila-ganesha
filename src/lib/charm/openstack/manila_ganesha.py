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
# import json
# import socket
# import subprocess

# import charms.reactive as reactive

import charms_openstack.charm
import charms_openstack.adapters
import charms_openstack.plugins
from charms_openstack.ip import resolve_address

# import charmhelpers.core as ch_core


MANILA_DIR = '/etc/manila/'
MANILA_CONF = MANILA_DIR + "manila.conf"
MANILA_LOGGING_CONF = MANILA_DIR + "logging.conf"
MANILA_API_PASTE_CONF = MANILA_DIR + "api-paste.ini"
CEPH_CONF = '/etc/ceph/ceph.conf'


@charms_openstack.adapters.config_property
def access_ip(config):
    """Return the list of lines from the backends that need to go into the
    various configuration files.

    This one is for manila.conf
    :returns list of lines: the config for the manila.conf file
    """
    return config.charm_instance.access_ip


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


class GaneshaCharmRelationAdapters(
        charms_openstack.adapters.OpenStackRelationAdapters):
    relation_adapters = {
        'amqp': charms_openstack.adapters.RabbitMQRelationAdapter,
        'ceph': charms_openstack.plugins.CephRelationAdapter,
        'manila-gahesha': charms_openstack.adapters.OpenStackRelationAdapter,
        'identity-service': KeystoneCredentialAdapter,
        'shared_db': charms_openstack.adapters.DatabaseRelationAdapter,
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
    group = 'manila'
    adapters_class = GaneshaCharmRelationAdapters
    ceph_key_per_unit_name = True
    services = [
        'nfs-ganesha',
        'manila-share',
    ]
    ha_resources = ['vips', 'dnsha']
    release_pkg = 'manila-common'

    package_codenames = {
        'manila-common': collections.OrderedDict([
            ('7', 'rocky'),
            ('8', 'stein'),
            ('9', 'train'),
        ]),
    }

    @property
    def restart_map(self):
        return {
            MANILA_CONF: ['manila-share'],
            MANILA_API_PASTE_CONF: ['manila-share'],
            MANILA_LOGGING_CONF: ['manila-share'],
            CEPH_CONF: ['manila-share'],
        }

    @property
    def access_ip(self):
        return resolve_address()

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
