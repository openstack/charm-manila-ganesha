import subprocess

import charms.reactive as reactive

import charms_openstack.bus
import charms_openstack.charm as charm
import charms.reactive.relations as relations

import charmhelpers.core as ch_core
from charmhelpers.core.hookenv import log


charms_openstack.bus.discover()

# Use the charms.openstack defaults for common states and hooks
charm.use_defaults(
    'charm.installed',
    'amqp.connected',
    'cluster.available',
    'shared-db.connected',
    'config.changed',
    'update-status',
    'upgrade-charm',
    'certificates.available',
)


@reactive.when('ceph.connected')
@reactive.when_not('ceph.available')
def ceph_connected(ceph):
    ceph.create_pool(ch_core.hookenv.service_name())
    with charm.provide_charm_instance() as charm_instance:
        charm_instance.request_ceph_permissions(ceph)


@reactive.when('manila-plugin.available')
def setup_manila():
    manila_relation = relations.endpoint_from_flag('manila-plugin.available')
    manila_relation.name = 'cephfsnfs1'
    manila_relation.configuration_data = {
        'complete': True,
    }


@reactive.when_not('identity-service.available')
@reactive.when('identity-service.connected')
def configure_ident_username(keystone):
    """Requests a user to the Identity Service
    """
    username = 'manila'
    keystone.request_credentials(username)


@reactive.when('ceph.available',
               'amqp.available',
               'manila-plugin.available',
               'shared-db.available',
               'identity-service.available',
               )
def render_things(*args):
    with charm.provide_charm_instance() as charm_instance:
        ceph_relation = relations.endpoint_from_flag('ceph.available')
        if not ceph_relation.key:
            ch_core.hookenv.log(
                (
                    'Ceph endpoint "{}" flagged available yet '
                    'no key.  Relation is probably departing.'
                ).format(ceph_relation.relation_name),
                level=ch_core.hookenv.INFO)
            return
        ch_core.hookenv.log('Ceph endpoint "{}" available, configuring '
                            'keyring'.format(ceph_relation.relation_name),
                            level=ch_core.hookenv.INFO)

        charm_instance.configure_ceph_keyring(ceph_relation.key)
        charm_instance.render_with_interfaces(args)
        for service in charm_instance.services:
            ch_core.host.service('enable', service)
            ch_core.host.service('start', service)
        reactive.set_flag('config.rendered')
        charm_instance.assess_status()


@reactive.when('config.rendered')
@reactive.when_not('ha.connected')
def enable_services_in_non_ha():
    with charm.provide_charm_instance() as charm_instance:
        for service in charm_instance.services:
            ch_core.host.service('enable', service)
            ch_core.host.service('start', service)


@reactive.when_all('config.rendered',
                   'ceph.pools.available')
@reactive.when_not('ganesha-pool-configured')
def configure_ganesha(*args):
    cmd = [
        'rados', '-p', 'manila-ganesha', '--id', 'manila-ganesha',
        'put', 'ganesha-export-index', '/dev/null'
    ]
    try:
        subprocess.check_call(cmd)
        reactive.set_flag('ganesha-pool-configured')
    except subprocess.CalledProcessError:
        log("Failed to setup ganesha index object")


@reactive.when('ha.connected', 'ganesha-pool-configured',
               'config.rendered')
def cluster_connected(hacluster):
    """Configure HA resources in corosync"""
    with charm.provide_charm_instance() as this_charm:
        this_charm.configure_ha_resources(hacluster)
        for service in ['nfs-ganesha', 'manila-share']:
            ch_core.host.service('disable', service)
            ch_core.host.service('stop', service)
        hacluster.add_systemd_service('nfs-ganesha',
                                      'nfs-ganesha',
                                      clone=False)
        hacluster.add_systemd_service('manila-share',
                                      'manila-share',
                                      clone=False)
        # This is a bit of a nasty hack to ensure that we can colocate the
        # services to make manila + ganesha colocate. This can be tidied up
        # once
        # https://bugs.launchpad.net/charm-interface-hacluster/+bug/1880644
        # is resolved
        import hooks.relations.hacluster.common as hacluster_common  # noqa
        crm = hacluster_common.CRM()
        crm.colocation('ganesha_with_vip',
                       'inf',
                       'res_nfs_ganesha_nfs_ganesha',
                       'grp_ganesha_vips')
        crm.colocation('manila_with_vip',
                       'inf',
                       'res_manila_share_manila_share',
                       'grp_ganesha_vips')
        hacluster.manage_resources(crm)
        this_charm.assess_status()
