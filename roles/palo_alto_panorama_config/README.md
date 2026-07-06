# palo_alto_panorama_config

This role handles Panorama-related onboarding.

It has two entry points:

- `tasks/firewall.yml`: runs on the firewall to point it at Panorama and set the Panorama auth key.
- `tasks/main.yml`: runs against Panorama to add firewalls to managed devices, device groups, and template stacks.

## Firewall-Side Tasks

`firewall.yml`:

- Sets the firewall's local Panorama server.
- Retrieves a Panorama auth key.
- Applies the auth key on the firewall.

This is included by `palo_alto_bootstrap` when `add_to_panorama` is true.

## Panorama-Side Tasks

`main.yml`:

- Adds each firewall serial number as a Panorama managed device.
- Adds each firewall to the configured device group.
- Adds each firewall to the configured template stack.
- Commits Panorama if onboarding changed anything.

## Key Inputs

- `panorama_settings.host`
- `panorama_settings.public_fqdn`
- `panorama_settings.api_key`
- `panorama_settings.device_group`
- `panorama_settings.template_stack`
- firewall entries with `hostname` and `serial`

## Notes

HA and most local network/security configuration should come from Panorama templates and device groups when `add_to_panorama` is true. The exception is advanced routing enablement, which is handled locally by `palo_alto_bootstrap`.

