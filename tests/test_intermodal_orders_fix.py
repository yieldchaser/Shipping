import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "md_cleanup"))
import intermodal_orders_fix as F  # noqa: E402

HDR = "| Units | Type | Size | Yard | Delivery | Buyer | Price | Comments |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n"
PDF = ("Units Type Size Yard Delivery Buyer Price Comments 4 Tanker 158,000 dwt New Times, China 2024-2025 "
       "Greek (TMS Cardiff) $70.0m 2+2 PCC 4,500 ceu CMJL Nanjing, China 2028-2029 Norwegian (UECC) undisclosed "
       "LNG, Battery Hybrid www.intermodal.gr 6")


def test_lost_delivery_read_from_pdf():
    md = HDR + "| 4 | Tanker | 158,000 | dwt | New Times, China | Greek (TMS Cardiff) | \\$70.0m |  |\n"
    out, notes = F.fix_text(md, PDF)
    assert "| 4 | Tanker | 158,000 dwt | New Times, China | 2024-2025 | Greek (TMS Cardiff) | \\$70.0m |  |" in out
    assert not notes


def test_lost_comments_read_from_pdf():
    md = HDR + "| 2+2 | PCC | 4,500 | ceu | CMJL Nanjing, China | 2028-2029 | Norwegian (UECC) | undisclosed |\n"
    out, _ = F.fix_text(md, PDF)
    assert "| 2+2 | PCC | 4,500 ceu | CMJL Nanjing, China | 2028-2029 | Norwegian (UECC) | undisclosed | LNG, Battery Hybrid |" in out


def test_split_header_loses_nothing():
    md = ("| Units | Type | Size | Size | Yard | Delivery | Buyer | Price | Comments |\n"
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
          "| 2 | PCC | 7,000 | ceu | GSI, China | 2028 | Swiss (GCC) | undisclosed | LNG |\n")
    out, _ = F.fix_text(md, "")
    assert out.splitlines()[0] == "| Units | Type | Size | Yard | Delivery | Buyer | Price | Comments |"
    assert out.splitlines()[2] == "| 2 | PCC | 7,000 ceu | GSI, China | 2028 | Swiss (GCC) | undisclosed | LNG |"


def test_value_not_found_is_left_blank():
    md = HDR + "| 4 | Tanker | 158,000 | dwt | Unknown Yard | Greek (X) | \\$1.0m |  |\n"
    out, notes = F.fix_text(md, PDF)
    assert "| 4 | Tanker | 158,000 dwt | Unknown Yard |  | Greek (X) | \\$1.0m |  |" in out
    assert notes


def test_clean_table_untouched():
    md = HDR + "| 4 | Tanker | 158,000 dwt | New Times, China | 2025 | Greek (X) | \\$70.0m |  |\n"
    assert F.fix_text(md, PDF)[0] == md
