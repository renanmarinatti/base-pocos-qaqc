import hashlib

import pytest

from pocos.collect import check_published, resolve
from pocos.inventory import well_name_from_file


def test_sodir_file_carries_snapshot_date():
    url, path = resolve({"tabela_sodir": "wellbore_core", "arquivo": "sodir/core_{snapshot}.csv"}, "2026-10-31")
    assert "tableview/wellbore_core&" in url
    assert path.name == "core_2026-10-31.csv"


def test_published_checksum_mismatch_fails(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"poco")
    check_published(f, "md5:" + hashlib.md5(b"poco").hexdigest())
    with pytest.raises(RuntimeError):
        check_published(f, "md5:" + "0" * 32)


@pytest.mark.parametrize(
    ("file", "well"),
    [("15_9-13.las", "15/9-13"), ("16_1-6 A.las", "16/1-6 A"), ("16_11-1 ST3.las", "16/11-1 ST3")],
)
def test_well_name_from_file(file, well):
    assert well_name_from_file(file) == well
