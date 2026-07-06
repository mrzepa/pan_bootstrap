#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import re
import sys
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
import urllib3
import yaml


DEFAULT_HOST = "192.168.4.62"

EXPORT_PARENTS = [
    {
        "category": "certificates",
        "xpath": "/config/shared/certificate",
    },
    {
        "category": "certificate_profiles",
        "xpath": "/config/shared/certificate-profile",
    },
    {
        "category": "external_dynamic_lists",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/external-list",
    },
    {
        "category": "anti_spyware_profiles",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/profiles/spyware",
    },
    {
        "category": "vulnerability_profiles",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/profiles/vulnerability",
    },
    {
        "category": "url_filtering_profiles",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/profiles/url-filtering",
    },
    {
        "category": "file_blocking_profiles",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/profiles/file-blocking",
    },
    {
        "category": "wildfire_analysis_profiles",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/profiles/wildfire-analysis",
    },
    {
        "category": "antivirus_profiles",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/profiles/virus",
    },
    {
        "category": "data_filtering_profiles",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/profiles/data-filtering",
    },
    {
        "category": "security_profile_groups",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/profile-group",
    },
    {
        "category": "log_forwarding_profiles",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/log-settings/profiles",
    },
]

VOLATILE_ATTRS = {"admin", "dirtyId", "oldname", "time", "uuid"}


class LiteralString(str):
    pass


class IndentDumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def literal_representer(dumper: yaml.Dumper, data: LiteralString):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.SafeDumper.add_representer(LiteralString, literal_representer)
yaml.SafeDumper.add_multi_representer(LiteralString, literal_representer)
IndentDumper.add_representer(LiteralString, literal_representer)
IndentDumper.add_multi_representer(LiteralString, literal_representer)


def load_env(path: Path) -> dict[str, str]:
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def clean_xml(node: ET.Element) -> None:
    for attr in VOLATILE_ATTRS:
        node.attrib.pop(attr, None)
    for child in list(node):
        clean_xml(child)


def indent_xml(node: ET.Element) -> None:
    ET.indent(node, space="  ")


def entry_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "unnamed"


class PanosXmlApi:
    def __init__(self, host: str, username: str, password: str, timeout: int = 30):
        self.host = host.replace("https://", "").replace("http://", "").strip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.key = self.keygen()

    @property
    def base_url(self) -> str:
        return f"https://{self.host}/api/"

    def keygen(self) -> str:
        response = self.session.get(
            self.base_url,
            params={"type": "keygen", "user": self.username, "password": self.password},
            timeout=self.timeout,
        )
        root = ET.fromstring(response.text)
        if root.attrib.get("status") != "success":
            raise RuntimeError(f"PAN-OS keygen failed: {response.text}")
        key = root.findtext("./result/key")
        if not key:
            raise RuntimeError("PAN-OS keygen response did not include an API key")
        return key

    def get(self, xpath: str) -> ET.Element:
        response = self.session.get(
            self.base_url,
            params={"type": "config", "action": "get", "xpath": xpath, "key": self.key},
            timeout=self.timeout,
        )
        root = ET.fromstring(response.text)
        if root.attrib.get("status") != "success":
            raise RuntimeError(f"PAN-OS config get failed for {xpath}: {response.text}")
        return root


def child_text(node: ET.Element, path: str) -> str | None:
    value = node.findtext(path)
    return value.strip() if value and value.strip() else None


def member_text(node: ET.Element, path: str) -> str | None:
    value = child_text(node, f"{path}/member")
    return value


def export_edl(entry: ET.Element) -> dict[str, object]:
    type_node = entry.find("./type")
    edl_type = list(type_node)[0].tag if type_node is not None and list(type_node) else None
    data = list(type_node)[0] if type_node is not None and list(type_node) else ET.Element("empty")
    item = {
        "name": entry.attrib["name"],
        "edl_type": edl_type,
        "source": child_text(data, "./url"),
        "certificate_profile": child_text(data, "./certificate-profile"),
        "description": child_text(data, "./description"),
        "state": "present",
    }
    recurring = data.find("./recurring")
    if recurring is not None and list(recurring):
        repeat_node = list(recurring)[0]
        item["repeat"] = "weekly" if repeat_node.tag == "weekly" else repeat_node.tag
        item["repeat_at"] = child_text(repeat_node, "./at")
        item["repeat_day_of_week"] = child_text(repeat_node, "./day-of-week")
        item["repeat_day_of_month"] = child_text(repeat_node, "./day-of-month")
    return {key: value for key, value in item.items() if value is not None}


def export_profile_group(entry: ET.Element) -> dict[str, object]:
    return {
        key: value
        for key, value in {
            "pg_name": entry.attrib["name"],
            "virus": member_text(entry, "./virus"),
            "spyware": member_text(entry, "./spyware"),
            "vulnerability": member_text(entry, "./vulnerability"),
            "url_filtering": member_text(entry, "./url-filtering"),
            "file_blocking": member_text(entry, "./file-blocking"),
            "data_filtering": member_text(entry, "./data-filtering"),
            "wildfire": member_text(entry, "./wildfire-analysis"),
            "state": "present",
        }.items()
        if value is not None
    }


def export_log_forwarding_profile(entry: ET.Element) -> dict[str, object]:
    spec = xml_entry_to_spec(entry, root=True)
    return {"name": entry.attrib["name"], "spec": spec}


def xml_entry_to_spec(element: ET.Element, *, root: bool = False):
    spec = {
        f"@{key}": value
        for key, value in element.attrib.items()
        if not (root and key == "name")
    }
    children = list(element)
    if children:
        grouped = {}
        for child in children:
            grouped.setdefault(child.tag, []).append(xml_entry_to_spec(child))
        for tag, values in grouped.items():
            spec[tag] = values if tag == "entry" or len(values) > 1 else values[0]
    elif element.text and element.text.strip():
        return element.text.strip()
    return spec


def export_certificate(entry: ET.Element, certificate_dir: Path) -> dict[str, object]:
    name = entry.attrib["name"]
    public_key = child_text(entry, "./public-key")
    if not public_key:
        raise RuntimeError(f"Certificate {name} does not include a public key")
    certificate_dir.mkdir(parents=True, exist_ok=True)
    certificate_path = certificate_dir / f"{entry_name(name)}.pem"
    certificate_path.write_text(public_key + "\n", encoding="utf-8")
    return {
        "name": name,
        "file": certificate_path.as_posix(),
        "format": "pem",
        "state": "present",
    }


def export_entries(api: PanosXmlApi, certificate_dir: Path) -> dict[str, list[dict[str, object]]]:
    output = {
        "security_default_certificates": [],
        "security_default_external_dynamic_lists": [],
        "security_default_profile_groups": [],
        "security_default_log_forwarding_profiles": [],
        "security_default_config_elements": [],
    }
    for parent in EXPORT_PARENTS:
        root = api.get(parent["xpath"])
        entries = root.findall(".//result/*/entry")
        for entry in entries:
            name = entry.attrib.get("name", "")
            if not name:
                continue
            category = parent["category"]
            if category == "certificates":
                output["security_default_certificates"].append(export_certificate(entry, certificate_dir))
                continue
            if category == "external_dynamic_lists":
                output["security_default_external_dynamic_lists"].append(export_edl(entry))
                continue
            if category == "security_profile_groups":
                output["security_default_profile_groups"].append(export_profile_group(entry))
                continue
            if category == "log_forwarding_profiles":
                output["security_default_log_forwarding_profiles"].append(export_log_forwarding_profile(entry))
                continue
            clean_xml(entry)
            indent_xml(entry)
            element = ET.tostring(entry, encoding="unicode").strip() + "\n"
            output["security_default_config_elements"].append(
                {
                    "name": f"{parent['category']}_{entry_name(name)}",
                    "category": parent["category"],
                    "xpath": parent["xpath"],
                    "element": LiteralString(element),
                }
            )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--output", default="vars/security_defaults.yml")
    parser.add_argument("--certificate-dir", default="files/certificates")
    args = parser.parse_args()

    env = load_env(Path(args.env_file))
    username = os.environ.get("FW_USERNAME") or env.get("USERNAME")
    password = os.environ.get("FW_PASSWORD") or env.get("PASSWORD")
    if not username or not password:
        print("FW_USERNAME/FW_PASSWORD or USERNAME/PASSWORD in .env are required", file=sys.stderr)
        return 2

    api = PanosXmlApi(args.host, username, password)
    output = export_entries(api, Path(args.certificate_dir))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = textwrap.dedent(
        f"""\
        ---
        # Generated from lab firewall {args.host}.
        # Re-run tools/export_security_defaults.py after updating the source objects.
        """
    )
    body = yaml.dump(output, Dumper=IndentDumper, sort_keys=False, width=120, default_flow_style=False)
    output_path.write_text(header + body, encoding="utf-8")
    total = sum(len(items) for items in output.values())
    print(f"Exported {total} security default items to {output_path}")
    print(f"certificates: {len(output['security_default_certificates'])}")
    print(f"external_dynamic_lists: {len(output['security_default_external_dynamic_lists'])}")
    print(f"profile_groups: {len(output['security_default_profile_groups'])}")
    print(f"log_forwarding_profiles: {len(output['security_default_log_forwarding_profiles'])}")
    for category in sorted({item["category"] for item in output["security_default_config_elements"]}):
        count = sum(1 for item in output["security_default_config_elements"] if item["category"] == category)
        print(f"{category}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
