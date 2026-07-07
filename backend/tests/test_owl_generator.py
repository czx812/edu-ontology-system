import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.owl_generator import generate_owl


class OwlGeneratorTests(unittest.TestCase):
    def test_generate_owl_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = generate_owl(
                {"classes": [{"name": "Student"}], "relations": [], "properties": []},
                export_dir=tmp_dir,
            )
            self.assertTrue(Path(output_path).exists())


if __name__ == "__main__":
    unittest.main()
