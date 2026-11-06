import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

from archive_audit import verify_archive
from bundle import add_tree


class ArchiveFormat(unittest.TestCase):
    def test_round_trip_modes_links_bytes_and_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            subprocess.run(["git","init","-q",str(r)],check=True)
            d = r/"upstream"
            (d/"bin").mkdir(parents=True)
            run = d/"bin"/"run"
            run.write_bytes(b"#!/bin/sh\nexit 0\n")
            run.chmod(0o755)
            (d/"bin.txt").write_bytes(b"plain")
            os.symlink("bin/run",d/"current")
            subprocess.run(["git","-C",str(r),"add","upstream"],check=True)
            subprocess.run(["git","-C",str(r),"-c","user.name=Test","-c","user.email=test@example.org",
                            "commit","-qm","fixture"],check=True)
            tree = subprocess.check_output(["git","-C",str(r),"rev-parse","HEAD:upstream"],text=True).strip()
            archive = r/"good.zip"
            with zipfile.ZipFile(archive,"w") as z:
                add_tree(z,r,"HEAD","","upstream")
            self.assertEqual(verify_archive(archive,"atlas-opsbook/upstream/",tree),tree)
            with zipfile.ZipFile(archive) as source, zipfile.ZipFile(r/"bad.zip","w") as z:
                for entry in source.infolist():
                    data = source.read(entry)
                    if entry.filename.endswith("/run"):
                        entry.external_attr = 0o100644 << 16
                    z.writestr(entry,data)
            with self.assertRaisesRegex(ValueError,"Tree mismatch"):
                verify_archive(r/"bad.zip","atlas-opsbook/upstream/",tree)
