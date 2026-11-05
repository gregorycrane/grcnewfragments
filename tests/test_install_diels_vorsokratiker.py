from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location("install_diels", ROOT / "tools/install_diels_vorsokratiker.py")
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def records(volume):
    source = ROOT / "sources/volumes/diels" / f"diels.vorsokratiker.vol{volume}.xml"
    return MODULE.split_volume(source, volume)[0]


def test_heraclitus_uses_dk_item_numbers_not_pages():
    fragments, labels = MODULE.fragmentize_pages(records(1)["12"]["pages"], 1, "12")

    assert labels[:3] == ["A1", "A1a", "A2"]
    assert "B1" in labels
    assert "B139" in labels
    assert "C1" in labels
    assert all(fragment.get("subtype") == "fragment" for fragment in fragments)
    assert not any(
        node.get("subtype") == "page"
        for fragment in fragments
        for node in fragment.iter(MODULE.q("div"))
    )
    assert sum(1 for fragment in fragments for _ in fragment.iter(MODULE.q("pb"))) == 47


def test_composite_running_head_does_not_move_last_b_fragments_into_c():
    _, labels = MODULE.fragmentize_pages(records(1)["12"]["pages"], 1, "12")

    assert labels.index("B138") < labels.index("B139") < labels.index("C1")
    assert "C138" not in labels
    assert "C139" not in labels


def test_single_unnumbered_dk_section_gets_implied_a1():
    fragments, labels = MODULE.fragmentize_pages(records(1)["6"]["pages"], 1, "6")

    assert labels == ["A1"]
    assert any(True for _ in fragments[0].iter(MODULE.q("pb")))


def test_refs_decl_is_fragment_citable():
    refs = MODULE.refs_decl()
    cite = refs.find(MODULE.q("citeStructure"))
    pattern = refs.find(MODULE.q("cRefPattern"))

    assert cite.get("unit") == "fragment"
    assert "subtype='fragment'" in cite.get("match")
    assert pattern.get("n") == "fragment"
    assert "subtype='fragment'" in pattern.get("replacementPattern")
