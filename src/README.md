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

## Spaces

This charm can optionally dedicate a provider's physical
network to serving Ganesha NFS shares. It does so through its
support for Juju spaces.

The charm uses a space called `tenant-storage` and it should be accessible
(routed is ok) to all tenants that expect to access the Manila shares. The
easiest way to ensure this access is to create a provider network in OpenStack
that is mapped to the same network layer as this space is. For example, the
storage space is mapped to VLAN 120, then an OpenStack administrator should
create a provider network that maps to the same VLAN. For example:

    openstack network create \
        --provider-network-type vlan \
        --provider-segment 120 \
        --share \
        --provider-physical-network physnet1 \
        tenant-storage
    openstack subnet create tenant \
        --network=tenant-storage \
        --subnet-range 10.1.10.0/22 \
        --gateway 10.1.10.1 \
        --allocation-pool start=10.1.10.50,end=10.1.13.254

When creating the space in MAAS that corresponds to this network, be sure that
DHCP is disabled in this space. If MAAS performs any additional allocations in
this space, ensure that the range configured for the subnet in Neutron does not
overlap with the MAAS subnets.

If dedicating a network space is not desired, it is also possible to use
Ganesha over a routed network. Manila's IP access restrictions will still be
used to secure access to Ganesha even if the network is not a Neutron managed
network.

# Bugs

Please report bugs on [Launchpad](https://bugs.launchpad.net/charm-manila-ganesha/+filebug).

For general questions please refer to the OpenStack [Charm Guide](https://github.com/openstack/charm-guide).
