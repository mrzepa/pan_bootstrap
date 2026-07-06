# Palo Alto Firewall Bootstrap

Ansible project for bootstrapping Palo Alto Networks firewalls from staging management IPs.

The project supports a single standalone firewall, a local active/passive HA pair, and optional Panorama onboarding. A small local web GUI is included to generate the input YAML, but the playbook itself is CLI-first and runs from this repository.

## What This Builds

For every firewall, the bootstrap can:

- refresh licenses
- install content and anti-virus updates
- upgrade PAN-OS to the requested version
- set telemetry region and hostname
- optionally enable PAN-OS advanced routing
- remove factory-default objects that conflict with a clean baseline
- disable SIP ALG
- commit pending changes

For standalone firewalls, it can also build a usable initial local configuration:

- logical router or virtual router routing path
- internet and internal zones
- Layer 3 internet and internal interfaces
- static, DHCP, or PPPoE internet addressing
- non-SD-WAN default routes
- optional SD-WAN for two to four internet uplinks
- outbound PAT rules
- zone protection, interface management, and LLDP profiles
- DNS, NTP, timezone, and login banner
- dynamic update schedules
- External Dynamic Lists, security profiles, profile groups, and log forwarding
- baseline block and allow security policy rules
- reserved default security rule overrides

For Panorama-managed firewalls, the local bootstrap points the firewall at Panorama and sets the auth key. The Panorama phase adds the device to managed devices, the target device group, and the target template stack.

## Safety Notes

This project is intended for new or factory-reset firewalls. It removes factory defaults and applies opinionated bootstrap settings.

Advanced routing is optional. When selected, it is a local firewall lifecycle change that requires a local commit and reboot. The API-driven flow used here does not migrate existing virtual router configuration into logical router configuration. If existing routing must be preserved, convert advanced routing from the PAN-OS GUI first so PAN-OS can perform the migration workflow.

The generated default security policy blocks interzone traffic except for the explicit bootstrap allow rules. Site-specific security policy must be reviewed and extended after bootstrap.

## Requirements

- Python 3
- Ansible
- Palo Alto Networks firewall API access from the machine running the playbook
- A staging management IP for each firewall
- A target PAN-OS version

Install dependencies from the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml -p ./collections
```

Collections are installed into the project-local `collections/` directory so the playbook does not depend on user-level Ansible content under `~/.ansible`.

## Quick Start

Copy an example input file:

```bash
cp vars/firewalls.example.yml vars/firewalls.yml
```

For a local HA pair:

```bash
cp vars/firewalls.ha.example.yml vars/firewalls.yml
```

Edit `vars/firewalls.yml`, then run:

```bash
source .venv/bin/activate
ansible-playbook playbooks/bootstrap_firewalls.yml
```

The playbook prompts once for the firewall password and uses that password for all staged firewalls in the run. Do not store firewall passwords in `vars/firewalls.yml`.

Use a different input file:

```bash
ansible-playbook playbooks/bootstrap_firewalls.yml -e input_file=/path/to/firewalls.yml
```

Run a syntax check:

```bash
ansible-playbook playbooks/bootstrap_firewalls.yml --syntax-check
```

## Input File

The default input file is `vars/firewalls.yml`.

Required common inputs:

- `panos_version`
- `firewalls[].hostname`
- `firewalls[].staging_ip`
- `firewalls[].role`

Common optional inputs:

- `firewall_username`, default `admin`
- `telemetry_region`, default `ca`
- `advanced_routing_enabled`, default `false`
- `deployment_mode`, default `standalone`
- `logical_router_name`
- `system_settings.timezone`
- `system_settings.dns_primary`
- `system_settings.dns_secondary`
- `system_settings.ntp_primary`
- `system_settings.ntp_secondary`

Deployment modes:

- `standalone`: exactly one firewall with role `standalone`
- `ha_pair`: exactly two firewalls, one `primary` and one `secondary`

When more than one firewall is present, the firewall bootstrap phase runs in parallel. Input validation and optional Panorama onboarding run on `localhost` and are intentionally sequential.

## Advanced Routing

Advanced routing is controlled by:

```yaml
advanced_routing_enabled: false
logical_router_name: default
```

Set `advanced_routing_enabled: true` only when you want the bootstrap to enable PAN-OS advanced routing locally. This is available for standalone and Panorama-managed deployments because Panorama cannot perform this local enablement step by itself.

When advanced routing is enabled for a standalone firewall, the standalone role creates the logical router named by `logical_router_name`. When the firewall is Panorama-managed, logical router configuration should come from Panorama templates after the local advanced-routing lifecycle step is complete.

This has been validated against PAN-OS 11.2. Validate new major or minor PAN-OS trains before using advanced routing broadly.

## Standalone Networking

Standalone networking is configured from the `network:` input block. At minimum, define one internet zone, one internal zone, one internet interface, and one internal interface.

Example:

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

Internet interfaces support:

- `static`: requires `ip_address` and `default_gateway`
- `dhcp`
- `pppoe`: requires `pppoe_username` and `pppoe_password`

If SD-WAN is enabled, define two to four internet interfaces. The role checks for the SD-WAN license before applying SD-WAN configuration.

## Panorama Onboarding

Set `add_to_panorama: true` and provide:

```yaml
panorama:
  host: panorama.example.com
  public_fqdn: panorama.example.com
  api_key: change-me
  device_group: Example-Device-Group
  template_stack: Example-Template-Stack
```

Each firewall also needs a `serial`.

When Panorama is enabled, local standalone network and security baseline configuration is not applied. HA configuration is expected to come from Panorama templates. Advanced routing remains a local optional bootstrap step because Panorama cannot complete it on its own.

## Local HA

Local HA is used only when:

```yaml
deployment_mode: ha_pair
add_to_panorama: false
```

Required HA inputs:

- `ha.ha1_interface`
- `ha.ha2_interface`
- `ha.group_id`

Defaults:

- primary HA1 IP: `169.254.0.1`
- secondary HA1 IP: `169.254.0.2`
- netmask: `255.255.255.252`
- primary priority: `90`
- secondary priority: `101`
- preemptive: `true`

Set `firewalls[].management_ip` when backup HA1 should use a management IP that is different from the staging IP.

All HA tasks are tagged `ha`, so they can be selected or skipped with Ansible tags.

## Security Defaults

Standalone security defaults are stored in `vars/security_defaults.yml`.

The role applies:

- certificate files from `files/certificates/`
- External Dynamic Lists
- certificate profiles
- anti-spyware, vulnerability, URL filtering, antivirus, file blocking, and WildFire profiles
- security profile groups
- log forwarding profiles

Certificates are checked before import. The play fails if a certificate PEM is expired. Replace expired roots or intermediates with current certificates from the issuing CA before retrying.

These defaults are maintained as project data. Add or change defaults in YAML using supported collection modules first, REST-backed custom objects second, and structured config custom modules only when needed.

## Web GUI

The GUI generates the YAML consumed by `playbooks/bootstrap_firewalls.yml`.

Start it from the project root:

```bash
python3 webgui_server.py
```

Open:

```text
http://127.0.0.1:8081/
```

The GUI can save directly to `vars/firewalls.yml`, which is ignored by git.

## Project Layout

- `playbooks/bootstrap_firewalls.yml`: main playbook
- `roles/palo_alto_bootstrap`: common firewall lifecycle
- `roles/palo_alto_standalone_config`: standalone local firewall baseline
- `roles/palo_alto_sdwan`: standalone SD-WAN configuration
- `roles/palo_alto_ha`: local active/passive HA
- `roles/palo_alto_panorama_config`: Panorama onboarding
- `library/`: custom Ansible modules
- `vars/firewalls.example.yml`: standalone example input
- `vars/firewalls.ha.example.yml`: HA example input
- `vars/security_defaults.yml`: standalone security defaults
- `webgui/`: local YAML generator UI

Each role has its own README with role-specific details.

## Validation

Useful development checks:

```bash
python3 -m py_compile library/*.py
ANSIBLE_LOCAL_TEMP=.ansible/tmp .venv/bin/ansible-playbook playbooks/bootstrap_firewalls.yml --syntax-check
ANSIBLE_LOCAL_TEMP=.ansible/tmp .venv/bin/ansible-lint
```

## License

MIT
