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
ansible-galaxy collection install -r requirements.yml
```

The `paloaltonetworks.panos` Galaxy collection provides the PAN-OS Ansible modules used by the playbook. The Python requirements include Ansible plus the PAN helper libraries used by the custom modules in `library/`.

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

The baseline config runs on every firewall by staging IP:

- Set hostname
- Remove default security rule, virtual/logical router, virtual wire, trust/untrust zones, and ethernet1/1-1/2 defaults
- Disable SIP ALG
- Set telemetry region
- Optionally connect to Panorama and set auth key
- Remove default Threats scheduler override
- Refresh license
- Update content and antivirus
- Commit pending config
- Upgrade PAN-OS to the requested version and wait for API return

For HA pairs without Panorama, the playbook also configures active/passive HA after the common baseline. For HA pairs with Panorama, no local HA configuration is applied because HA is expected to come from the Panorama template.

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
