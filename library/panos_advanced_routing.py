#!/usr/bin/python

from __future__ import annotations

import xml.etree.ElementTree as ET

import requests
import urllib3
from ansible.module_utils.basic import AnsibleModule


DOCUMENTATION = r"""
---
module: panos_advanced_routing
short_description: Manage PAN-OS advanced routing mode
description:
  - Enables or disables PAN-OS advanced routing through the XML API.
  - This module exists because the Palo Alto Networks Ansible collection does not yet expose advanced routing settings.
  - Tested against PAN-OS 11.2. Validate newer PAN-OS versions before broad use.
  - This module does not migrate virtual router configuration to logical router configuration.
options:
  ip_address:
    description:
      - Firewall management IP address or FQDN.
    type: str
    required: true
  username:
    description:
      - Firewall username. Required when I(api_key) is not supplied.
    type: str
  password:
    description:
      - Firewall password. Required when I(api_key) is not supplied.
    type: str
  api_key:
    description:
      - Existing PAN-OS API key.
    type: str
  enabled:
    description:
      - Desired advanced routing state.
    type: bool
    default: true
  validate_certs:
    description:
      - Validate the firewall HTTPS certificate.
    type: bool
    default: false
  timeout:
    description:
      - HTTP request timeout in seconds.
    type: int
    default: 30
author:
  - mrzepa
"""

EXAMPLES = r"""
- name: Enable advanced routing
  panos_advanced_routing:
    ip_address: 192.0.2.10
    username: admin
    password: "{{ firewall_password }}"
    enabled: true
"""

RETURN = r"""
previous:
  description: Previous advanced routing state.
  returned: always
  type: bool
current:
  description: Current advanced routing state after the module runs.
  returned: always
  type: bool
"""


ADVANCED_ROUTING_DIRECT_XPATH = (
    "/config/devices/entry[@name='localhost.localdomain']"
    "/deviceconfig/setting/advance-routing"
)
ADVANCED_ROUTING_PARENT_XPATH = (
    "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/setting"
)


class PanosApiError(Exception):
    pass


class PanosXmlApi:
    def __init__(self, module: AnsibleModule):
        self.module = module
        self.host = module.params["ip_address"].replace("https://", "").replace("http://", "").strip("/")
        self.verify = module.params["validate_certs"]
        self.timeout = module.params["timeout"]
        self.api_key = module.params["api_key"]

        if not self.verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    @property
    def base_url(self) -> str:
        return f"https://{self.host}/api/"

    def request(self, params: dict[str, str]) -> ET.Element:
        if not self.api_key:
            self.api_key = self.keygen()

        request_params = {"key": self.api_key}
        request_params.update(params)

        response = requests.get(
            self.base_url,
            params=request_params,
            verify=self.verify,
            timeout=self.timeout,
        )
        root = ET.fromstring(response.text)
        status = root.attrib.get("status")
        if status != "success":
            message = root.findtext("./msg/line") or root.findtext("./msg") or response.text
            raise PanosApiError(message)
        return root

    def keygen(self) -> str:
        username = self.module.params["username"]
        password = self.module.params["password"]
        if not username or not password:
            self.module.fail_json(msg="username and password are required when api_key is not supplied")

        response = requests.get(
            self.base_url,
            params={
                "type": "keygen",
                "user": username,
                "password": password,
            },
            verify=self.verify,
            timeout=self.timeout,
        )
        root = ET.fromstring(response.text)
        status = root.attrib.get("status")
        if status != "success":
            message = root.findtext("./msg/line") or root.findtext("./msg") or response.text
            self.module.fail_json(msg=f"PAN-OS keygen failed with HTTP {response.status_code}: {message}")

        key = root.findtext("./result/key")
        if not key:
            self.module.fail_json(msg="PAN-OS keygen response did not include an API key")
        return key

    def get_advanced_routing(self) -> bool:
        direct_root = self.request(
            {
                "type": "config",
                "action": "get",
                "xpath": ADVANCED_ROUTING_DIRECT_XPATH,
            }
        )
        direct = direct_root.find("./result/advance-routing")
        if direct is not None and direct.text is not None:
            return direct.text.strip().lower() in ("yes", "true", "on", "1")
        return False

    def set_advanced_routing(self, enabled: bool) -> None:
        if not enabled:
            self.delete_advanced_routing()
            return

        value = "yes" if enabled else "no"
        self.request(
            {
                "type": "config",
                "action": "set",
                "xpath": ADVANCED_ROUTING_PARENT_XPATH,
                "element": f"<advance-routing>{value}</advance-routing>",
            }
        )

    def delete_advanced_routing(self) -> None:
        self.request(
            {
                "type": "config",
                "action": "delete",
                "xpath": ADVANCED_ROUTING_DIRECT_XPATH,
            }
        )

def run_module():
    module = AnsibleModule(
        argument_spec={
            "ip_address": {"type": "str", "required": True},
            "username": {"type": "str"},
            "password": {"type": "str", "no_log": True},
            "api_key": {"type": "str", "no_log": True},
            "enabled": {"type": "bool", "default": True},
            "validate_certs": {"type": "bool", "default": False},
            "timeout": {"type": "int", "default": 30},
        },
        required_one_of=[["api_key", "username"]],
        required_together=[["username", "password"]],
        supports_check_mode=True,
    )

    desired = module.params["enabled"]
    api = PanosXmlApi(module)

    try:
        previous = api.get_advanced_routing()
        changed = previous != desired

        if changed and not module.check_mode:
            api.set_advanced_routing(desired)

        module.exit_json(
            changed=changed,
            previous=previous,
            current=desired if changed else previous,
            msg=(
                f"Advanced routing would be set to {desired}"
                if changed and module.check_mode
                else f"Advanced routing is {desired}"
            ),
        )
    except requests.RequestException as exc:
        module.fail_json(msg=f"HTTP error talking to PAN-OS XML API: {exc.__class__.__name__}")
    except ET.ParseError as exc:
        module.fail_json(msg=f"Could not parse PAN-OS XML API response: {exc}")
    except PanosApiError as exc:
        module.fail_json(msg=f"PAN-OS XML API request failed: {exc}")


if __name__ == "__main__":
    run_module()
