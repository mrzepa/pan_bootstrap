#!/usr/bin/python

from __future__ import annotations

import ssl
import time
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule


DOCUMENTATION = r"""
---
module: check_certificate_validity
short_description: Validate a PEM certificate before importing it into PAN-OS
description:
  - Parses a local PEM certificate and fails if it is expired or expires before the configured minimum validity window.
options:
  path:
    description:
      - Local path to the PEM certificate file.
    required: true
    type: path
  minimum_valid_days:
    description:
      - Minimum number of days the certificate must remain valid.
      - Use C(0) to fail only when the certificate is already expired.
    default: 0
    type: int
author:
  - Local project
"""

EXAMPLES = r"""
- name: Validate certificate before import
  check_certificate_validity:
    path: files/certificates/GTS-Root-R1.pem
    minimum_valid_days: 0
"""

RETURN = r"""
not_after:
  description: Certificate expiration time.
  returned: success
  type: str
days_remaining:
  description: Whole days remaining before expiration.
  returned: success
  type: int
"""


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "path": {"type": "path", "required": True},
            "minimum_valid_days": {"type": "int", "default": 0},
        },
        supports_check_mode=True,
    )

    cert_path = Path(module.params["path"])
    minimum_valid_days = module.params["minimum_valid_days"]

    if not cert_path.exists():
        module.fail_json(msg=f"Certificate file does not exist: {cert_path}")

    try:
        cert_info = ssl._ssl._test_decode_cert(str(cert_path))
    except Exception as exc:
        module.fail_json(msg=f"Unable to parse PEM certificate {cert_path}: {exc}")

    not_after = cert_info.get("notAfter")
    if not not_after:
        module.fail_json(msg=f"Certificate {cert_path} does not include a notAfter value")

    try:
        expires_at = ssl.cert_time_to_seconds(not_after)
    except Exception as exc:
        module.fail_json(msg=f"Unable to parse expiration for certificate {cert_path}: {exc}")

    now = time.time()
    seconds_remaining = expires_at - now
    days_remaining = int(seconds_remaining // 86400)
    required_seconds = minimum_valid_days * 86400

    if seconds_remaining < required_seconds:
        recommendation = (
            "Download current intermediate and root certificates from the issuing CA, "
            "replace the PEM files, then re-run the security defaults export or bootstrap."
        )
        if seconds_remaining < 0:
            reason = "expired"
        else:
            reason = f"expires within {minimum_valid_days} day(s)"
        module.fail_json(
            msg=f"Certificate {cert_path} is {reason}. {recommendation}",
            not_after=not_after,
            days_remaining=days_remaining,
        )

    module.exit_json(changed=False, not_after=not_after, days_remaining=days_remaining)


if __name__ == "__main__":
    main()
