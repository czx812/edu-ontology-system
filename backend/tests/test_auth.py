import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.auth import AuthStore


class AuthStoreTests(unittest.TestCase):
    def test_register_and_login_flow(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = AuthStore(storage_path=Path(tmp_dir) / "users.json")
            user = store.register_user("alice", "secret123")
            self.assertEqual(user["username"], "alice")

            token = store.create_token(user["id"])
            self.assertTrue(token)

            session_user = store.get_user_by_token(token)
            self.assertEqual(session_user["username"], "alice")

            self.assertTrue(store.verify_password("alice", "secret123"))
            self.assertFalse(store.verify_password("alice", "wrong"))


if __name__ == "__main__":
    unittest.main()
