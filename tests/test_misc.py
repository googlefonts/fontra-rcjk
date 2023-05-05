import pytest

from fontra_rcjk.base import makeSafeLayerName


@pytest.mark.parametrize(
    "layerName, expectedSafeLayerName",
    [
        ("a", "a"),
        ("a" * 50, "a" * 50),
        ("á" * 50, "á" * 50),
        ("a" * 51, "a" * 37 + ".bfc5fe0e3601"),
        ("á" * 51, "á" * 37 + ".3c1a18fbe650"),
        ("a/b", "a_b.c14cddc033f6"),
        ("a+b", "a_b.300273daf0bb"),
        ("a👀b", "a_b.6815aba75bec"),
    ],
)
def test_safeLayerName(layerName, expectedSafeLayerName):
    safeLayerName = makeSafeLayerName(layerName)
    assert expectedSafeLayerName == safeLayerName
