# Manila Ganesha

This charm provides Ganesha with CephFS as a storage backend for Manila, OpenStack's shared filesystem service.

# Usage

Manila (plus manila-ganesha) relies on services from the mysql/percona,
rabbitmq-server, keystone charms, and a storage backend charm.  The following
yaml file will create a small, unconfigured, OpenStack system with the
necessary components to start testing with Manila.  Note that these target the
'next' OpenStack charms which are essentially 'edge' charms.

```yaml
# Juju 2.0 deploy bundle for development ('next') charms
# UOSCI relies on this for OS-on-OS deployment testing
series: bionic
automatically-retry-hooks: False
services:
  ceph-mon:
    charm: cs:~openstack-charmers-next/ceph-mon
    num_units: 3
    options:
      source: *source
  ceph-osd:
    charm: cs:~openstack-charmers-next/ceph-osd
    num_units: 3
    options:
      source: *source
      osd-devices: /dev/sdb
  ceph-fs:
    charm: cs:~openstack-charmers-next/ceph-fs
    num_units: 2
    options:
      source: *source
  mysql:
    charm: cs:~openstack-charmers-next/percona-cluster
    num_units: 1
    constraints: mem=1G
    options:
      dataset-size: 50%
      root-password: mysql
  rabbitmq-server:
    charm: cs:~openstack-charmers-next/rabbitmq-server
    num_units: 1
    constraints: mem=1G
  keystone:
    charm: cs:~openstack-charmers-next/keystone
    num_units: 1
    constraints: mem=1G
    options:
      admin-password: openstack
      admin-token: ubuntutesting
      preferred-api-version: "2"
  glance:
    charm: cs:~openstack-charmers-next/glance
    num_units: 1
    constraints: mem=1G
  nova-cloud-controller:
    charm: cs:~openstack-charmers-next/nova-cloud-controller
    num_units: 1
    constraints: mem=1G
    options:
      network-manager: Neutron
  nova-compute:
    charm: cs:~openstack-charmers-next/nova-compute
    num_units: 1
    constraints: mem=4G
  neutron-gateway:
    charm: cs:~openstack-charmers-next/neutron-gateway
    num_units: 1
    constraints: mem=1G
    options:
      bridge-mappings: physnet1:br-ex
      instance-mtu: 1300
  neutron-api:
    charm: cs:~openstack-charmers-next/neutron-api
    num_units: 1
    constraints: mem=1G
    options:
      neutron-security-groups: True
      flat-network-providers: physnet1
  neutron-openvswitch:
    charm: cs:~openstack-charmers-next/neutron-openvswitch
  cinder:
    charm: cs:~openstack-charmers-next/cinder
    num_units: 1
    constraints: mem=1G
    options:
      block-device: vdb
      glance-api-version: 2
      overwrite: 'true'
      ephemeral-unmount: /mnt
  manila:
    charm: cs:~openstack-charmers-next/manila
    num_units: 1
    options:
      debug: True
  manila-ganesha:
      charm: cs:~openstack-charmers-next/manila-ganesha
    options:
      debug: True
relations:
  - [ ceph-mon, ceph-osd ]
  - [ ceph-mon, ceph-fs ]
  - [ ceph-mon, manila-ganesha ]
  - [ keystone, mysql ]
  - [ manila, mysql ]
  - [ manila, rabbitmq-server ]
  - [ manila, keystone ]
  - [ manila, manila-generic ]
  - [ glance, keystone]
  - [ glance, mysql ]
  - [ glance, "cinder:image-service" ]
  - [ nova-compute, "rabbitmq-server:amqp" ]
  - [ nova-compute, glance ]
  - [ nova-cloud-controller, rabbitmq-server ]
  - [ nova-cloud-controller, mysql ]
  - [ nova-cloud-controller, keystone ]
  - [ nova-cloud-controller, glance ]
  - [ nova-cloud-controller, nova-compute ]
  - [ cinder, keystone ]
  - [ cinder, mysql ]
  - [ cinder, rabbitmq-server ]
  - [ cinder, nova-cloud-controller ]
  - [ "neutron-gateway:amqp", "rabbitmq-server:amqp" ]
  - [ neutron-gateway, nova-cloud-controller ]
  - [ neutron-api, mysql ]
  - [ neutron-api, rabbitmq-server ]
  - [ neutron-api, nova-cloud-controller ]
  - [ neutron-api, neutron-openvswitch ]
  - [ neutron-api, keystone ]
  - [ neutron-api, neutron-gateway ]
  - [ neutron-openvswitch, nova-compute ]
  - [ neutron-openvswitch, rabbitmq-server ]
  - [ neutron-openvswitch, manila ]
```

and then (with juju 2.x):

```bash
    juju deploy manila.yaml
```

Note that this OpenStack system will need to be configured (in terms of
networking, images, etc.) before testing can commence.

# Bugs

Please report bugs on [Launchpad](https://bugs.launchpad.net/charm-manila-ganesha/+filebug).

For general questions please refer to the OpenStack [Charm Guide](https://github.com/openstack/charm-guide).
