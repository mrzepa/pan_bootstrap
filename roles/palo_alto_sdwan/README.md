# palo_alto_sdwan

This role configures the standalone firewall SD-WAN baseline for two to four internet interfaces.

The role is included by `palo_alto_standalone_config` when `network.sdwan.enabled` is true and the firewall has two to four internet interfaces.

## What It Does

- Checks that the firewall reports the `Feature: SD WAN` license.
- Creates ISP link tags named `ISP1`, `ISP2`, and so on.
- Creates SD-WAN interface profiles for each internet link.
- Enables SD-WAN link settings on each internet interface.
- Adds SD-WAN gateway metadata for static internet interfaces.
- Creates the SD-WAN aggregate interface, default `sdwan.1`.
- Creates a default route through `sdwan.1` in either the logical router or virtual router path.
- Creates traffic distribution profiles:
  - `ISP1-ISP2`
  - `ISP2-ISP1`
  - `BEST-AVAILABLE`
- Creates the default SD-WAN policy rule.

## Key Inputs

- `palo_alto_sdwan_internet_interfaces`
- `palo_alto_sdwan_internet_zones`
- `palo_alto_sdwan_internal_zones`
- `palo_alto_sdwan_interface_name`, default `sdwan.1`
- `palo_alto_sdwan_distribution_profile`, default `BEST-AVAILABLE`
- `palo_alto_sdwan_rule_name`, default `Best Path`
- `palo_alto_sdwan_rule_tag`, default `SDWAN`

## Implementation Rules

Use supported `paloaltonetworks.panos` modules first. If the collection does not support a needed SD-WAN setting, use REST through `panos_rest_object`. Use structured custom modules such as `panos_config_entry` only when neither the collection nor REST covers the setting.

Do not add raw XML to role YAML.

