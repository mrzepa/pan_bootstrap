# Palo Alto Firewall Bootstrap

Standalone Ansible project for bootstrapping one Palo Alto firewall or an HA pair from staging management IPs.

This project mirrors the useful PAN steps from `well_site_ansible_v2` without Freshservice, NetBox, or Aruba Central dependencies.

## Inputs

## Install Dependencies

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml -p ./collections
```

The `paloaltonetworks.panos` Galaxy collection provides the PAN-OS Ansible modules used by the playbook. Collections are installed into the project-local `collections/` directory so a fresh clone does not depend on user-level Ansible content under `~/.ansible`. The Python requirements include Ansible plus the PAN helper libraries used by the custom advanced-routing module in `library/`.

Copy the example input file and edit it:

```bash
cp vars/firewalls.example.yml vars/firewalls.yml
```

For a local HA pair, start from:

```bash
cp vars/firewalls.ha.example.yml vars/firewalls.yml
```

Required inputs:

- `firewalls[].staging_ip`
- `firewalls[].hostname`
- `panos_version`
- `firewall_username`, defaults to `admin` when omitted
- `telemetry_region`, defaults to `ca` for Canada
- `advanced_routing_enabled`, defaults to `true`
- `logical_router_name`, defaults to `default` when advanced routing is enabled
- `deployment_mode`: `standalone` or `ha_pair`
- `firewalls[].role`: `standalone`, `primary`, or `secondary`

Optional Panorama onboarding:

- Set `add_to_panorama: true`
- Fill `panorama.host`, `panorama.public_fqdn`, `panorama.api_key`, `panorama.device_group`, and `panorama.template_stack`
- Add `serial` for each firewall

Local HA bootstrap:

- Used only when `deployment_mode: ha_pair` and `add_to_panorama: false`
- Required: `ha.ha1_interface`, `ha.ha2_interface`, and `ha.group_id`
- Optional defaults: primary HA1 `169.254.0.1`, secondary HA1 `169.254.0.2`, netmask `255.255.255.252`, primary priority `90`, secondary priority `101`, and preemptive `true`
- Set `firewalls[].management_ip` when backup HA1 should use a management IP different from `staging_ip`
- If `ha.ha1_interface` or `ha.ha2_interface` starts with `ethernet`, the playbook converts that interface to PAN-OS HA mode before applying HA

## Run

```bash
source .venv/bin/activate
ansible-playbook playbooks/bootstrap_firewalls.yml
```

The playbook prompts once for the firewall password and uses that same password for every firewall in the run. Do not put firewall passwords in `vars/firewalls.yml`.

When more than one firewall is present, the firewall bootstrap phase runs in parallel. The playbook uses Ansible's `free` strategy for the dynamic `firewalls_to_bootstrap` hosts, and `ansible.cfg` sets `forks = 20` so multiple staged firewalls can progress independently. The input validation and optional Panorama onboarding phases run on `localhost` and are intentionally sequential.

Use a different input file:

```bash
ansible-playbook playbooks/bootstrap_firewalls.yml -e input_file=/path/to/firewalls.yml
```

Check syntax:

```bash
ansible-playbook playbooks/bootstrap_firewalls.yml --syntax-check
```

## Current Scope

The common bootstrap lifecycle runs on every firewall by staging IP:

- Set hostname
- Enable advanced routing
- Remove default security rule, default virtual router, default logical router, virtual wire, trust/untrust zones, and ethernet1/1-1/2 defaults
- Disable SIP ALG
- Set telemetry region
- Remove default Threats scheduler override
- Refresh license
- Update content and antivirus
- Include standalone-only or Panorama-specific configuration roles
- Commit pending config
- Upgrade PAN-OS to the requested version and wait for API return

`palo_alto_standalone_config` runs only when `add_to_panorama: false` and currently handles local logical router creation, dynamic update schedules, SD-WAN bootstrap, and exported local security defaults from `vars/security_defaults.yml`.

It can also configure basic standalone networking from the `network:` input block: internet/internal zones, layer 3 interface addressing, non-SD-WAN default routes, optional SD-WAN link setup for two to four internet uplinks, outbound PAT rules, an `Unsanctioned_Apps` application group, known-bad-list block rules, high-risk region geo-blocking for `CN`, `KP`, `NG`, and `RU`, and default rule logging/action overrides. Default security policy rules include descriptions and grouping tags. The standalone profile baseline creates the `PING` interface management profile, enables LLDP globally, applies `LLDP-PR` to non-internet interfaces, applies `Internet-ZoneProtect-Protect` to internet zones, and applies `Internal-Zone-Protect` to every other zone. The SD-WAN role checks for the SD WAN license, creates ISP tags and interface profiles, enables SD-WAN link settings on the internet interfaces, creates `sdwan.1`, adds the default route through `sdwan.1`, creates traffic distribution profiles, and installs the default SD-WAN policy.

Standalone system settings default primary and secondary DNS to `1.1.1.1` and `1.0.0.1`, primary and secondary NTP to `0.pool.org` and `1.pool.org`, a browser-guessed timezone in the GUI, and a login banner warning that unauthorized access is prohibited. The baseline also creates allow rules for approved DNS, approved NTP, and Palo Alto Networks update services.

`palo_alto_panorama_config` handles Panorama-related work. During the firewall bootstrap phase it points the firewall at Panorama and sets the auth key. In the localhost Panorama phase it adds the device to Panorama, the target device group, and the target template stack.

For HA pairs without Panorama, the playbook also configures active/passive HA after the common baseline. For HA pairs with Panorama, no local HA configuration is applied because HA is expected to come from the Panorama template.

## Advanced Routing

The bootstrap enables PAN-OS advanced routing by default with `advanced_routing_enabled: true`, whether or not the firewall will later be onboarded to Panorama. This is a local firewall lifecycle change that requires a local commit and reboot, so Panorama cannot complete it on its own. This module has been validated against PAN-OS 11.2. Because Palo Alto may change advanced-routing configuration storage across PAN-OS versions, keep this setting explicit in `vars/firewalls.yml` and validate new major/minor PAN-OS trains before using it broadly.

Use this API-driven flow for new firewalls or devices where existing routing configuration can be discarded. It only changes the advanced routing system setting; it does not migrate virtual router configuration into logical router configuration. If a firewall already has virtual router settings that must be preserved, perform the advanced routing conversion from the PAN-OS GUI first so PAN-OS can handle the migration workflow.

When advanced routing is enabled for standalone firewalls, the bootstrap creates a logical router named by `logical_router_name`, which defaults to `default`. Panorama-managed firewalls should receive logical router configuration from templates after the local advanced-routing lifecycle step is complete.

## Dynamic Updates

For standalone firewalls, the bootstrap installs the latest content and anti-virus updates during the initial run, then configures recurring dynamic update schedules. By default, Applications and Threats run daily at `01:00` with download-and-install and a 48-hour new App-ID threshold, anti-virus runs hourly with download-and-install, and WildFire runs every minute with download-and-install. Panorama-managed firewalls should receive dynamic update schedules from Panorama templates or device settings. Set `palo_alto_standalone_config_dynamic_update_schedule_enabled: false` to skip local schedule management.

## Security Defaults

`vars/security_defaults.yml` contains exported baseline objects for local, non-Panorama-managed firewalls. Supported objects are stored as structured YAML for collection modules, including certificates, External Dynamic Lists, security profile groups, and log forwarding profiles. Certificate PEM data is kept in `files/certificates/` and referenced from YAML so roots and intermediates can be inspected and replaced without editing a large YAML document. Unsupported objects remain as XML config elements, currently the certificate profile and the threat/security profile definitions.

To refresh this file from the lab firewall:

```bash
FW_USERNAME=admin FW_PASSWORD='change-me' .venv/bin/python tools/export_security_defaults.py --host 192.168.4.62
```

The `palo_alto_standalone_config` role applies these after license refresh, content updates, and anti-virus updates, then the common bootstrap commits the imported objects with the rest of the run. Certificates are validated before import and the play fails if a PEM is expired. Replace expired roots or intermediates with current certificates from the issuing CA before retrying. Certificate imports and XML fallback objects are applied before EDLs so EDLs can reference the certificate profile, and profile groups are applied after the security profiles exist. Set `palo_alto_standalone_config_security_defaults_enabled: false` to skip this baseline.

## HA Completion Work

The remaining HA hardening items are:

- Add optional HA timers if the site standard needs non-default failover timing
- Add optional HA authentication/key settings if required
- Add post-checks for HA state, peer visibility, config sync status, and active/passive role
- Add explicit sync-from-primary behavior if desired after both peers have committed local HA

All HA tasks are tagged `ha`, so they can be included or excluded with `--tags ha` or `--skip-tags ha`.

## Web GUI

The project is CLI-first for execution, but `webgui/index.html` provides a small local input generator for `vars/firewalls.yml`.

Run the local GUI server from the project root:

```bash
python3 webgui_server.py
```

Open `http://127.0.0.1:8081/`. The GUI can save the generated input directly to `vars/firewalls.yml`, which is ignored by git.

## License

MIT
