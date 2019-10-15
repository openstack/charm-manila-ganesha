import charms.reactive as reactive

import charms_openstack.bus
import charms_openstack.charm as charm
import charms.reactive.relations as relations

import charmhelpers.core as ch_core


charms_openstack.bus.discover()

# Use the charms.openstack defaults for common states and hooks
charm.use_defaults(
    'charm.installed',
    'amqp.connected',
    'shared-db.connected',
    # 'identity-service.connected',
    'config.changed',
    'update-status',
    'upgrade-charm',
    'certificates.available',
)


@reactive.when('ceph.connected')
@reactive.when_not('ceph.available')
def ceph_connected(ceph):
    ceph.create_pool(ch_core.hookenv.service_name())


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

        charm_instance.configure_ceph_keyring(ceph_relation.key())
        charm_instance.render_with_interfaces(args)
        for service in charm_instance.services:
            ch_core.host.service('enable', service)
            ch_core.host.service('start', service)
        reactive.set_flag('config.rendered')
        charm_instance.assess_status()
