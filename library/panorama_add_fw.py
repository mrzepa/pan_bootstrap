#!/usr/bin/python

import os
from ansible.module_utils.basic import AnsibleModule
from pypanrestv2.Base import Panorama
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _device_already_managed(pano, fw_serial):
    resp = pano.xml_request(
        params={
            "key": pano.api_key,
            "type": "config",
            "action": "get",
            "xpath": f"/config/mgt-config/devices/entry[@name='{fw_serial}']",
        }
    )
    response = resp.get("response", {}) if isinstance(resp, dict) else {}
    result = response.get("result", {}) if isinstance(response, dict) else {}
    entry = result.get("entry") if isinstance(result, dict) else None
    if isinstance(entry, list):
        return any(isinstance(item, dict) and item.get("@name") == fw_serial for item in entry)
    return isinstance(entry, dict) and entry.get("@name") == fw_serial


def run_module():
    module_args = {
        "pano_ip": {"type": "str", "required": True},
        "pano_api_key": {"type": "str", "required": True, "no_log": True},
        "fw_serial": {"type": "str", "required": True},
    }

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    pano_ip = module.params["pano_ip"]
    pano_api_key = module.params["pano_api_key"]
    fw_serial = module.params["fw_serial"]

    try:
        # Initialize Panorama connection
        pano = Panorama(pano_ip, api_key=pano_api_key)

        if _device_already_managed(pano, fw_serial):
            module.exit_json(changed=False, msg=f"Device {fw_serial} is already managed by Panorama")

        if module.check_mode:
            module.exit_json(
                changed=True,
                msg=f"Check mode: would add device {fw_serial} to Panorama",
            )

        pano.add_device(fw_serial)
        module.exit_json(changed=True, msg=f"Successfully added device {fw_serial} to Panorama")

    except Exception as e:
        module.fail_json(msg=f"Error adding device {fw_serial} to Panorama: {str(e)}")


if __name__ == '__main__':
    run_module()
