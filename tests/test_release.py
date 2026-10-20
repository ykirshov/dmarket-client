"""Release invariants: monotonic versions and immutable retry-safe uploads."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "release_tool", Path(__file__).resolve().parents[1] / "tools" / "release.py"
)
assert spec is not None and spec.loader is not None
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def test_initial_and_patch_versions():
    assert release.select_version({}, "new", "0.1.0") == "0.1.0"
    assert release.select_version({"v0.1.9": "old", "unrelated": "old"}, "new", "0.1.0") == "0.1.10"
    assert release.select_version({"v0.1.9": "old"}, "new", "0.2.0") == "0.2.0"


def test_rerun_reuses_reserved_tag():
    assert release.select_version({"v0.1.0": "same", "v0.1.1": "other"}, "same", "0.1.0") == "0.1.0"


def test_ambiguous_tags_are_rejected():
    with pytest.raises(ValueError, match="Multiple"):
        release.select_version({"v0.1.0": "same", "v0.1.1": "same"}, "same", "0.1.0")


def test_partial_upload_can_be_resumed():
    local = {"package.whl": "abc", "package.tar.gz": "def"}
    remote = [{"filename": "package.whl", "digests": {"sha256": "abc"}}]
    assert release.needs_publication(local, [])
    assert release.needs_publication(local, remote)
    remote.append({"filename": "package.tar.gz", "digests": {"sha256": "def"}})
    assert not release.needs_publication(local, remote)


def test_changed_or_unexpected_pypi_artifact_is_rejected():
    with pytest.raises(ValueError, match="differs"):
        release.needs_publication(
            {"package.whl": "abc"}, [{"filename": "package.whl", "digests": {"sha256": "changed"}}]
        )
    with pytest.raises(ValueError, match="unexpected"):
        release.needs_publication({}, [{"filename": "package.whl", "digests": {"sha256": "abc"}}])


@pytest.mark.parametrize("value", ["v1.2.3", "1.2", "1.2.3rc1", "01.2.3", "1.2.3\n"])
def test_only_stable_versions_are_accepted(value):
    with pytest.raises(ValueError):
        release.version_tuple(value)


def test_distribution_metadata_and_uv_gitignore(tmp_path):
    import io
    import tarfile
    import zipfile

    metadata = b"Name: dmarket-client\nVersion: 0.1.0\n\n"
    with zipfile.ZipFile(tmp_path / "dmarket_client-0.1.0-py3-none-any.whl", "w") as archive:
        archive.writestr("dmarket_client-0.1.0.dist-info/METADATA", metadata)
    with tarfile.open(tmp_path / "dmarket_client-0.1.0.tar.gz", "w:gz") as archive:
        member = tarfile.TarInfo("dmarket_client-0.1.0/PKG-INFO")
        member.size = len(metadata)
        archive.addfile(member, io.BytesIO(metadata))
    (tmp_path / ".gitignore").write_text("*\n")
    assert len(release.distribution_hashes(tmp_path, "0.1.0")) == 2
    with pytest.raises(ValueError, match="name/version"):
        release.distribution_hashes(tmp_path, "0.1.1")
    (tmp_path / "unexpected.txt").write_text("not a distribution")
    with pytest.raises(ValueError, match="exactly"):
        release.distribution_hashes(tmp_path, "0.1.0")
