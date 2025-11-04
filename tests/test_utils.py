import hashlib
import tempfile
import pytest
from pathlib import Path
from icoscp_obspack.utils import get_hash_sum

test_files_data = {
    "empty_file": b"",
    "hello_world": b"hello world",
    "binary_file": b"\x00\x01\x02\x03\xff",
}


@pytest.fixture(scope="module")
def tmp_files():
    """Create temporary files for all test cases."""
    files = {}
    for name, content in test_files_data.items():
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(content)
        tmp.flush()
        files[name] = Path(tmp.name)
    yield files
    # Cleanup
    for f in files.values():
        f.unlink(missing_ok=True)


@pytest.mark.parametrize("file_key", list(test_files_data.keys()))
def test_get_hash_sum(file_key, tmp_files):
    """Check SHA256 hash output for multiple file types."""
    content = test_files_data[file_key]
    expected_hash = hashlib.sha256(content).hexdigest()
    result = get_hash_sum(tmp_files[file_key])
    assert result == expected_hash
