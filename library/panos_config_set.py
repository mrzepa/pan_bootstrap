#!/usr/bin/python

from __future__ import annotations

import xml.etree.ElementTree as ET

import requests
import urllib3
from ansible.module_utils.basic import AnsibleModule


DOCUMENTATION = r"""
---
module: panos_config_set
short_description: Set PAN-OS XML config from structured data
description:
  - Sets PAN-OS config elements from structured YAML when collection and REST coverage is unavailable.
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
  xpath:
    type: str
    required: true
  spec:
    type: dict
    required: true
  validate_certs:
    type: bool
    default: false
  timeout:
    type: int
    default: 30
"""

VOLATILE_ATTRS = {"admin", "dirtyId", "time", "uuid", "oldname"}


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
        response = self.session.get(
            self.base_url,
            params={**params, "key": self.api_key},
            timeout=self.timeout,
        )
        root = ET.fromstring(response.text)
        if root.attrib.get("status") != "success":
            self.module.fail_json(msg=f"PAN-OS XML API failed: {response.text}")
        return root

    def get(self, xpath: str) -> ET.Element | None:
        root = self.request({"type": "config", "action": "get", "xpath": xpath})
        result = root.find("./result")
        if result is None or not list(result):
            return None
        return list(result)[0]

    def set(self, xpath: str, elements: list[ET.Element]) -> None:
        element = "".join(ET.tostring(item, encoding="unicode") for item in elements)
        self.request({"type": "config", "action": "set", "xpath": xpath, "element": element})


def append_value(parent: ET.Element, key: str, value) -> None:
    if key.startswith("@"):
        parent.set(key[1:], str(value))
        return
    if isinstance(value, list):
        for item in value:
            child = ET.SubElement(parent, key)
            append_spec(child, item)
        return
    child = ET.SubElement(parent, key)
    append_spec(child, value)


def append_spec(parent: ET.Element, spec) -> None:
    if isinstance(spec, dict):
        for key, value in spec.items():
            append_value(parent, key, value)
    elif spec is not None:
        parent.text = str(spec)


def build_elements(spec: dict) -> list[ET.Element]:
    elements = []
    for key, value in spec.items():
        element = ET.Element(key)
        append_spec(element, value)
        elements.append(element)
    return elements


def canonical(element: ET.Element | None):
    if element is None:
        return None
    attrs = tuple(sorted((key, value) for key, value in element.attrib.items() if key not in VOLATILE_ATTRS))
    return (
        element.tag,
        (element.text or "").strip() or None,
        attrs,
        [canonical(child) for child in list(element)],
    )


def run_module() -> None:
    module = AnsibleModule(
        argument_spec={
            "ip_address": {"type": "str", "required": True},
            "username": {"type": "str"},
            "password": {"type": "str", "no_log": True},
            "api_key": {"type": "str", "no_log": True},
            "xpath": {"type": "str", "required": True},
            "spec": {"type": "dict", "required": True},
            "validate_certs": {"type": "bool", "default": False},
            "timeout": {"type": "int", "default": 30},
        },
        required_one_of=[["api_key", "username"]],
        required_together=[["username", "password"]],
        supports_check_mode=True,
    )

    xpath = module.params["xpath"]
    desired = build_elements(module.params["spec"])
    api = PanosXmlApi(module)
    current = api.get(xpath)
    changed = current is None or [canonical(child) for child in desired] != [canonical(child) for child in list(current)]

    if changed and not module.check_mode:
        api.set(xpath, desired)

    module.exit_json(changed=changed)


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()
