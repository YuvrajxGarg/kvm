"""The parts of the Windows service that don't need Windows: its backend and agent build."""

import os
import shutil
import tempfile
import unittest

from kvm.store import Store
from kvm.winservice import HelperProxy, ServiceAgent


class ServiceParts(unittest.TestCase):
    def test_helper_proxy_builds_before_the_helper_reports(self):
        h = HelperProxy()
        self.assertEqual(h.screens.public(), [[0, 0, 1920, 1080]])
        self.assertFalse(h.permissions()["helper"])

    def test_service_agent_builds(self):
        tmp = tempfile.mkdtemp()
        try:
            a = ServiceAgent(HelperProxy(), Store(os.path.join(tmp, "svc")))
            self.assertIsNotNone(a)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
