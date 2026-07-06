# palo_alto_bootstrap

This role runs the common firewall bootstrap lifecycle for every firewall, whether the firewall will remain standalone or be managed by Panorama.

## What It Does

- Refreshes licenses.
- Installs content and anti-virus updates.
- Upgrades PAN-OS when `panos_version` is set and the firewall is not already running that version.
- Waits for the firewall to return after an OS upgrade reboot.
- Sets telemetry region and hostname.
- Enables or disables advanced routing locally.
- Removes factory-default objects that interfere with a clean baseline.
- Disables SIP ALG.
- Includes either `palo_alto_standalone_config` or `palo_alto_panorama_config` based on `add_to_panorama`.
- Commits pending firewall changes.

## Important Ordering

Licensing and dynamic content updates intentionally run before the PAN-OS upgrade and before configuration changes. Some firewall features and objects are unavailable until the license and content state is current.

Advanced routing is handled here instead of inside the standalone role because it requires a local firewall commit and reboot lifecycle. This must happen even when the firewall is later managed by Panorama.

## Key Inputs

- `panos_version`: target PAN-OS version.
- `firewall_info.hostname`: hostname to set.
- `firewall_info.staging_ip`: IP used by Ansible during bootstrap.
- `firewall_username` / `firewall_password`: local firewall credentials.
- `add_to_panorama`: selects standalone or Panorama-managed path.
- `palo_alto_bootstrap_telemetry_region`: telemetry/LCAAS region, default `ca`.
- `palo_alto_bootstrap_advanced_routing_enabled`: enables advanced routing when set to `true`, default `false`.

## Notes

When advanced routing is enabled, this process does not migrate virtual router configuration into a logical router. Use the PAN-OS GUI if an existing virtual router must be converted and preserved.
