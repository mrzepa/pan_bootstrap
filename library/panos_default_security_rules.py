#!/usr/bin/python

from __future__ import annotations

import xml.etree.ElementTree as ET

import requests
import urllib3
from ansible.module_utils.basic import AnsibleModule


DOCUMENTATION = r"""
---
module: panos_default_security_rules
short_description: Manage PAN-OS reserved default security rules
description:
  - Manages the reserved intrazone-default and interzone-default security rules.
  - PAN-OS does not expose these rules through the regular SecurityRules REST endpoint.
options:
  ip_address:
    type: str
    required: true
  username:
    type: str
  password:
    type: str
  api_key:
    type: str
  intrazone_profile_group:
    type: str
    required: true
  intrazone_log_forwarding:
    type: str
    required: true
  interzone_action:
    type: str
    choices:
      - drop
      - deny
      - reset-client
      - reset-server
      - reset-both
    default: drop
  validate_certs:
    type: bool
    default: false
  timeout:
    type: int
    default: 30
"""


class PanosXmlApi:
    def __init__(self, module: AnsibleModule) -> None:
        self.module = module
        self.host = module.params["ip_address"].replace("https://", "").replace("http://", "").strip("/")
        self.verify = module.params["validate_certs"]
        self.timeout = module.params["timeout"]
        self.api_key = module.params["api_key"]
        self.session = requests.Session()
        self.session.verify = self.verify
        if not self.verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    @property
    def base_url(self) -> str:
        return f"https://{self.host}/api/"

    def keygen(self) -> str:
        username = self.module.params["username"]
        password = self.module.params["password"]
        if not username or not password:
            self.module.fail_json(msg="username and password are required when api_key is not supplied")
        response = self.session.get(
            self.base_url,
            params={"type": "keygen", "user": username, "password": password},
            timeout=self.timeout,
        )
        root = ET.fromstring(response.text)
        if root.attrib.get("status") != "success":
            self.module.fail_json(msg=f"PAN-OS keygen failed: {response.text}")
        key = root.findtext("./result/key")
        if not key:
            self.module.fail_json(msg="PAN-OS keygen response did not include an API key")
        self.api_key = key
        return key

    def request(self, params: dict[str, str]) -> ET.Element:
        if not self.api_key:
            self.keygen()
        params = {**params, "key": self.api_key}
        response = self.session.get(self.base_url, params=params, timeout=self.timeout)
        root = ET.fromstring(response.text)
        if root.attrib.get("status") != "success":
            self.module.fail_json(msg=f"PAN-OS XML API failed: {response.text}")
        return root

    def get(self, xpath: str) -> ET.Element | None:
        root = self.request({"type": "config", "action": "get", "xpath": xpath})
        rules = root.find("./result/rules")
        return rules

    def edit(self, xpath: str, element: str) -> None:
        self.request({"type": "config", "action": "edit", "xpath": xpath, "element": element})


def rule_entry(name: str, children: list[ET.Element]) -> ET.Element:
    entry = ET.Element("entry", {"name": name})
    entry.extend(children)
    return entry


def text_element(name: str, text: str) -> ET.Element:
    element = ET.Element(name)
    element.text = text
    return element


def desired_rules(module: AnsibleModule) -> ET.Element:
    rules = ET.Element("rules")

    profile_setting = ET.Element("profile-setting")
    group = ET.SubElement(profile_setting, "group")
    member = ET.SubElement(group, "member")
    member.text = module.params["intrazone_profile_group"]

    rules.append(
        rule_entry(
            "intrazone-default",
            [
                text_element("action", "allow"),
                text_element("log-start", "no"),
                text_element("log-end", "yes"),
                profile_setting,
                text_element("log-setting", module.params["intrazone_log_forwarding"]),
            ],
        )
    )
    rules.append(
        rule_entry(
            "interzone-default",
            [
                text_element("action", module.params["interzone_action"]),
                text_element("log-start", "no"),
                text_element("log-end", "yes"),
            ],
        )
    )
    return rules


def canonical(element: ET.Element | None) -> list[tuple[str, str | None, tuple[tuple[str, str], ...], list]]:
    if element is None:
        return []
    ignored_attrs = {"admin", "dirtyId", "time", "uuid"}
    attrs = tuple(sorted((key, value) for key, value in element.attrib.items() if key not in ignored_attrs))
    return [
        (
            element.tag,
            (element.text or "").strip() or None,
            attrs,
            [canonical(child) for child in list(element)],
        )
    ]


def run_module() -> None:
    module = AnsibleModule(
        argument_spec={
            "ip_address": {"type": "str", "required": True},
            "username": {"type": "str"},
            "password": {"type": "str", "no_log": True},
            "api_key": {"type": "str", "no_log": True},
            "intrazone_profile_group": {"type": "str", "required": True},
            "intrazone_log_forwarding": {"type": "str", "required": True},
            "interzone_action": {
                "type": "str",
                "choices": ["drop", "deny", "reset-client", "reset-server", "reset-both"],
                "default": "drop",
            },
            "validate_certs": {"type": "bool", "default": False},
            "timeout": {"type": "int", "default": 30},
        },
        required_one_of=[["api_key", "username"]],
        required_together=[["username", "password"]],
        supports_check_mode=True,
    )

    xpath = "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/rulebase/default-security-rules/rules"
    api = PanosXmlApi(module)
    desired = desired_rules(module)
    current = api.get(xpath)
    changed = canonical(current) != canonical(desired)

    if changed and not module.check_mode:
        api.edit(xpath, ET.tostring(desired, encoding="unicode"))

    module.exit_json(changed=changed)


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()
