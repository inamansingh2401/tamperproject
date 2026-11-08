import os
import secrets
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gateway'))
from gateway import configure_credentials


class GatewayCredentialTests(unittest.TestCase):
    def test_only_environment_credentials_used_and_local_mode_needs_none(self):
        secret = secrets.token_urlsafe(40)
        with patch.dict(os.environ,SAFETRACK_DEVICE_KEY_GATEWAY=secret):
            config = configure_credentials({'device_key':'ignored-old-file-value'})
            self.assertEqual(config['device_key'],secret)
        self.assertNotIn('device_key',configure_credentials({'device_key':secret},local_only=True))

    def test_missing_or_arbitrary_environment_reference_rejected_without_echo(self):
        for config in ({'device_key_env':'JWT_SECRET'},{'device_key_env':'SAFETRACK_DEVICE_KEY_MISSING_TEST'}):
            with patch.dict(os.environ,{},clear=True):
                with self.assertRaises(ValueError) as error:
                    configure_credentials(config)
            self.assertNotIn(config['device_key_env'],str(error.exception))
