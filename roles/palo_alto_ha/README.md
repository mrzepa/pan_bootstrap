# palo_alto_ha

This role configures local active/passive HA for a two-firewall deployment when the firewalls are not managed by Panorama.

When `add_to_panorama` is true, HA is expected to come from Panorama templates, so this role should not be needed.

## What It Does

- Determines local and peer HA values from the firewall role, `primary` or `secondary`.
- Sets Ethernet HA links to interface type `ha` when the configured HA interface name starts with `ethernet`.
- Configures active/passive HA.
- Configures election priority and preempt behavior.
- Commits HA changes when pending changes exist.

All tasks are tagged `ha`, so they can be included or excluded with Ansible tags.

## Key Inputs

The role expects `ha_settings`, `firewall_info`, and `ha_peer_info` from the play:

- `ha_settings.ha1_interface`
- `ha_settings.ha2_interface`
- `ha_settings.group_id`
- `ha_settings.primary_ha1_ip`, default pattern `169.254.0.1`
- `ha_settings.secondary_ha1_ip`, default pattern `169.254.0.2`
- `ha_settings.netmask`, default `255.255.255.252`
- `ha_settings.primary_priority`, default `90`
- `ha_settings.secondary_priority`, default `101`
- `ha_settings.preemptive`, default `true`
- `firewall_info.management_ip` and `ha_peer_info.management_ip` for HA1 backup IPs

If `management_ip` is not set, the role falls back to each firewall's `staging_ip` for backup HA1.

## Notes

Dedicated HA interfaces can be referenced directly. If the platform does not have dedicated HA ports and Ethernet interfaces are used instead, the role changes those Ethernet interfaces to HA mode before applying HA settings.

