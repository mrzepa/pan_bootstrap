# palo_alto_standalone_config

This role builds the local baseline for standalone firewalls. It runs only when `add_to_panorama` is false.

The role owns local logical router creation, network interfaces and routes, standalone system settings, dynamic update schedules, security default objects, NAT policy, and baseline security policy.

## Task Layout

- `main.yml`: role orchestration and high-level ordering.
- `network.yml`: zones, Layer 3 interfaces, PPPoE settings, default routes, SD-WAN include, and NAT include.
- `network_profiles.yml`: interface management profile, zone protection profiles, LLDP profile, global LLDP enablement, and profile assignment.
- `object_tags.yml`: all policy/object tags used by NAT, security, and SD-WAN policy.
- `address_objects.yml`: address objects used by baseline policy rules.
- `application_objects.yml`: application groups used by baseline policy rules.
- `security_default_custom_objects.yml`: structured config or REST-backed security default objects that do not have clean first-class collection module support.
- `log_forwarding_profiles.yml`: log forwarding profiles defined in `vars/security_defaults.yml`.
- `nat_rules.yml`: outbound PAT rules.
- `security_rules.yml`: reserved default security rule overrides and baseline security policy rules.

## Ordering Rules

Keep the high-level order in `main.yml` intentional:

1. Create the logical router when advanced routing is enabled.
2. Configure network interfaces, profiles, SD-WAN, routes, and NAT.
3. Configure local system DNS, NTP, timezone, and login banner.
4. Configure recurring dynamic update schedules.
5. Load and apply security default objects.
6. Create tags, address objects, and application objects.
7. Create security policy rules.

Objects that rules reference must be created before the rules. For example, log forwarding profiles, security profile groups, tags, address objects, and application groups must exist before policy rules reference them.

## Adding Policy Rules

Add new security policy rules to `tasks/security_rules.yml`.

Baseline ordering should remain:

- Reserved default rule overrides at the top of the file.
- Block rules before allow rules.
- High-priority block rules near the top of the policy.
- Permit rules after the relevant block rules.

Use `location` and `existing_rule` deliberately. Prefer a stable chain such as:

```yaml
location: after
existing_rule: "Block Unsanctioned Apps"
```

Every new non-default policy rule should include:

- `description`
- `tag_name`
- `log_end: true`
- `log_setting: "{{ palo_alto_standalone_config_log_forwarding_profile }}"`
- explicit source and destination zones
- explicit applications and services

The reserved `intrazone-default` and `interzone-default` rules are exceptions. They are handled by the `panos_default_security_rules` custom module and should not get descriptions or tags.

If a new policy rule references a new tag, add the tag in `object_tags.yml` first. If it references a new address object, add it in `address_objects.yml`. If it references a new application group, add it in `application_objects.yml`.

## Adding NAT Rules

Add NAT rules to `tasks/nat_rules.yml`.

Do not create tags in `nat_rules.yml`; create them in `object_tags.yml`. NAT rules should include descriptions and tags just like security policy rules.

Current outbound PAT rules are generated from `network.internet_interfaces` and use the interface's `tags` value when present, or the role default NAT tag otherwise.

## Adding Network Config

Use `tasks/network.yml` for interface, route, zone, PPPoE, and routing-related tasks.

Use `tasks/network_profiles.yml` for reusable network profiles and their assignments, including:

- interface management profiles
- zone protection profiles
- LLDP profiles
- profile assignment to zones or interfaces

When adding routing changes, handle both routing modes when needed:

- Advanced routing enabled: use logical router modules such as `panos_logical_router_vrf_static_route`.
- Advanced routing disabled: use virtual router modules such as `panos_static_route`.

SD-WAN-specific work should normally go in `palo_alto_sdwan`, not this role, unless it is only orchestration around whether the SD-WAN role should be included.

## Adding Security Default Objects

The baseline security defaults live in `vars/security_defaults.yml`.

Use first-class `paloaltonetworks.panos` modules when available. Current examples include:

- certificates with `panos_import`
- External Dynamic Lists with `panos_edl`
- security profile groups with `panos_pg`

If the collection does not support an object cleanly, prefer REST with `panos_rest_object`. If REST does not cover the setting, use a structured custom module such as `panos_config_entry` or `panos_config_set`.

Do not add raw XML to YAML files. Store unsupported objects as structured dictionaries under `security_default_config_entries` or `security_default_rest_objects`.

These defaults are maintained as project data. Do not add workflows that regenerate them from a firewall.

## Network Input Shape

The role expects `palo_alto_standalone_config_network` to be derived from the top-level `network` input. The expected shape is:

```yaml
network:
  zones:
    - name: INTERNET
      type: internet
    - name: INSIDE
      type: internal
  internet_interfaces:
    - name: ethernet1/1
      zone: INTERNET
      address_type: dhcp
      tags:
        - ISP1
    - name: ethernet1/2
      zone: INTERNET
      address_type: static
      ip_address: 203.0.113.2/30
      default_gateway: 203.0.113.1
  internal_interfaces:
    - name: ethernet1/3
      zone: INSIDE
      ip_address: 192.168.1.1/24
  sdwan:
    enabled: false
    traffic_distribution: BEST-AVAILABLE
```

Internet interface `address_type` can be `static`, `dhcp`, or `pppoe`. Static internet interfaces need `ip_address` and `default_gateway`. PPPoE interfaces need `pppoe_username` and `pppoe_password`. Internal interfaces need `ip_address`.

Zones with `type: internet` receive the internet zone protection profile. All other zones receive the internal zone protection profile. LLDP is applied only to internal interfaces.

## Defaults And Toggles

Common toggles and defaults are in `defaults/main.yml`:

- `palo_alto_standalone_config_security_defaults_enabled`
- `palo_alto_standalone_config_dynamic_update_schedule_enabled`
- `palo_alto_standalone_config_policy_baseline_enabled`
- `palo_alto_standalone_config_known_bad_lists_enabled`
- `palo_alto_standalone_config_geo_blocking_enabled`
- `palo_alto_standalone_config_security_profile_group`
- `palo_alto_standalone_config_log_forwarding_profile`
- DNS, NTP, timezone, and login banner defaults

Use role-prefixed variable names for new defaults.

## Module Preference

When adding a new capability:

1. Use a supported `paloaltonetworks.panos` collection module.
2. If no collection module exists, use REST through `panos_rest_object`.
3. If REST is not available or cannot model the setting, use a structured custom module.

Avoid raw XML in Ansible YAML. The custom modules can talk XML API internally, but role YAML should remain structured and readable.
