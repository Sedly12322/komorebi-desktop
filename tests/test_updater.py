import hashlib
import tempfile
from pathlib import Path
import pytest
from wallhaven.updater import UpdateInfo, UpdateApplyWorker


def test_sha256_verification_success():
    with tempfile.NamedTemporaryFile("wb", delete=False) as f:
        f.write(b"Komorebi Desktop Test Binary Payload 12345")
        tmp_path = Path(f.name)

    try:
        expected = hashlib.sha256(b"Komorebi Desktop Test Binary Payload 12345").hexdigest()
        info = UpdateInfo(
            current_version="2.0.0",
            latest_version="2.1.0",
            checksums={"installer.exe": expected},
        )
        worker = UpdateApplyWorker(info)
        # Should not raise any exception
        worker._verify_sha256(tmp_path, "installer.exe")
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_sha256_verification_mismatch():
    with tempfile.NamedTemporaryFile("wb", delete=False) as f:
        f.write(b"Corrupted Data Content")
        tmp_path = Path(f.name)

    try:
        info = UpdateInfo(
            current_version="2.0.0",
            latest_version="2.1.0",
            checksums={"installer.exe": "0000000000000000000000000000000000000000000000000000000000000000"},
        )
        worker = UpdateApplyWorker(info)
        with pytest.raises(RuntimeError, match="SHA-256"):
            worker._verify_sha256(tmp_path, "installer.exe")
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
