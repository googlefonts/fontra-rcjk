import contextlib
from dataclasses import asdict
from importlib.metadata import entry_points
import pathlib
import pytest
from fontra.core.classes import VariableGlyph, from_dict


dataDir = pathlib.Path(__file__).resolve().parent / "data"


getGlyphTestData = [
    (
        "rcjk",
        {
            "axes": [
                {"defaultValue": 0.0, "maxValue": 1.0, "minValue": 0.0, "name": "HLON"},
                {"defaultValue": 0.0, "maxValue": 1.0, "minValue": 0.0, "name": "WGHT"},
            ],
            "name": "one_00",
            "sources": [
                {
                    "name": "<default>",
                    "location": {},
                    "layerName": "foreground",
                },
                {
                    "name": "longbar",
                    "location": {"HLON": 1.0},
                    "layerName": "longbar",
                },
                {
                    "name": "bold",
                    "location": {"WGHT": 1.0},
                    "layerName": "bold",
                },
            ],
            "layers": [
                {
                    "name": "foreground",
                    "glyph": {
                        "path": {
                            "coordinates": [
                                105,
                                0,
                                134,
                                0,
                                134,
                                600,
                                110,
                                600,
                                92,
                                600,
                                74,
                                598,
                                59,
                                596,
                                30,
                                592,
                                30,
                                572,
                                105,
                                572,
                            ],
                            "pointTypes": [0, 0, 0, 8, 2, 2, 8, 0, 0, 0],
                            "contourInfo": [{"endPoint": 9, "isClosed": True}],
                        },
                        "components": [],
                        "xAdvance": 229,
                    },
                },
                {
                    "name": "bold",
                    "glyph": {
                        "path": {
                            "coordinates": [
                                135,
                                0,
                                325,
                                0,
                                325,
                                600,
                                170,
                                600,
                                152,
                                600,
                                135,
                                598,
                                119,
                                596,
                                20,
                                582,
                                20,
                                457,
                                135,
                                457,
                            ],
                            "pointTypes": [0, 0, 0, 8, 2, 2, 8, 0, 0, 0],
                            "contourInfo": [{"endPoint": 9, "isClosed": True}],
                        },
                        "components": [],
                        "xAdvance": 450,
                    },
                },
                {
                    "name": "longbar",
                    "glyph": {
                        "path": {
                            "coordinates": [
                                175,
                                0,
                                204,
                                0,
                                204,
                                600,
                                180,
                                600,
                                152,
                                600,
                                124,
                                598,
                                99,
                                597,
                                0,
                                592,
                                0,
                                572,
                                175,
                                572,
                            ],
                            "pointTypes": [0, 0, 0, 8, 2, 2, 8, 0, 0, 0],
                            "contourInfo": [{"endPoint": 9, "isClosed": True}],
                        },
                        "components": [],
                        "xAdvance": 369,
                    },
                },
            ],
        },
    ),
    (
        "rcjk",
        {
            "axes": [
                {"defaultValue": 0.0, "maxValue": 1.0, "minValue": 0.0, "name": "wght"}
            ],
            "name": "uni0031",
            "sources": [
                {
                    "name": "<default>",
                    "location": {},
                    "layerName": "foreground",
                },
                {
                    "name": "wght",
                    "location": {"wght": 1.0},
                    "layerName": "wght",
                },
            ],
            "layers": [
                {
                    "name": "foreground",
                    "glyph": {
                        "path": {
                            "contourInfo": [],
                            "coordinates": [],
                            "pointTypes": [],
                        },
                        "components": [
                            {
                                "name": "DC_0031_00",
                                "transformation": {
                                    "rotation": 0,
                                    "scaleX": 1,
                                    "scaleY": 1,
                                    "tCenterX": 0,
                                    "tCenterY": 0,
                                    "translateX": -1,
                                    "translateY": 0,
                                },
                                "location": {"T_H_lo": 0, "X_X_bo": 0},
                            }
                        ],
                        "xAdvance": 350,
                    },
                },
                {
                    "name": "wght",
                    "glyph": {
                        "path": {
                            "contourInfo": [],
                            "coordinates": [],
                            "pointTypes": [],
                        },
                        "components": [
                            {
                                "name": "DC_0031_00",
                                "transformation": {
                                    "rotation": 0,
                                    "scaleX": 0.93,
                                    "scaleY": 1,
                                    "tCenterX": 0,
                                    "tCenterY": 0,
                                    "translateX": -23.0,
                                    "translateY": 0.0,
                                },
                                "location": {"T_H_lo": 0, "X_X_bo": 0.7},
                            }
                        ],
                        "xAdvance": 350,
                    },
                },
            ],
        },
    ),
    (
        "rcjk",
        {
            "axes": [
                {
                    "defaultValue": 0.0,
                    "maxValue": 1.0,
                    "minValue": 0.0,
                    "name": "X_X_bo",
                },
                {
                    "defaultValue": 0.0,
                    "maxValue": 1.0,
                    "minValue": 0.0,
                    "name": "X_X_la",
                },
            ],
            "name": "DC_0030_00",
            "sources": [
                {
                    "name": "<default>",
                    "location": {},
                    "layerName": "foreground",
                },
                {
                    "name": "X_X_bo",
                    "location": {"X_X_bo": 1.0},
                    "layerName": "X_X_bo_1_layer",
                },
                {
                    "name": "X_X_la",
                    "location": {"X_X_la": 1.0},
                    "layerName": "X_X_la_2_layer",
                },
            ],
            "layers": [
                {
                    "name": "foreground",
                    "glyph": {
                        "path": {
                            "contourInfo": [],
                            "coordinates": [],
                            "pointTypes": [],
                        },
                        "components": [
                            {
                                "location": {"WDTH": 0.33, "WGHT": 0.45},
                                "name": "zero_00",
                                "transformation": {
                                    "rotation": 0,
                                    "scaleX": 1,
                                    "scaleY": 1,
                                    "tCenterX": 0,
                                    "tCenterY": 0,
                                    "translateX": 0,
                                    "translateY": 0,
                                },
                            }
                        ],
                        "xAdvance": 600,
                    },
                },
                {
                    "name": "X_X_bo_1_layer",
                    "glyph": {
                        "path": {
                            "contourInfo": [],
                            "coordinates": [],
                            "pointTypes": [],
                        },
                        "components": [
                            {
                                "location": {"WDTH": 0.33, "WGHT": 1.0},
                                "name": "zero_00",
                                "transformation": {
                                    "rotation": 0,
                                    "scaleX": 1,
                                    "scaleY": 1,
                                    "tCenterX": 0,
                                    "tCenterY": 0,
                                    "translateX": 0,
                                    "translateY": 0,
                                },
                            }
                        ],
                        "xAdvance": 600,
                    },
                },
                {
                    "name": "X_X_la_2_layer",
                    "glyph": {
                        "path": {
                            "contourInfo": [],
                            "coordinates": [],
                            "pointTypes": [],
                        },
                        "components": [
                            {
                                "location": {"WDTH": 1.0, "WGHT": 0.45},
                                "name": "zero_00",
                                "transformation": {
                                    "rotation": 0,
                                    "scaleX": 1,
                                    "scaleY": 1,
                                    "tCenterX": 0,
                                    "tCenterY": 0,
                                    "translateX": 0,
                                    "translateY": 0,
                                },
                            }
                        ],
                        "xAdvance": 600,
                    },
                },
            ],
        },
    ),
]


testFontPaths = {
    "rcjk": dataDir / "figArnaud.rcjk",
}


def getTestFont(backendName):
    backendEntryPoints = entry_points(group="fontra.filesystem.backends")
    cls = backendEntryPoints[backendName].load()
    return cls.fromPath(testFontPaths[backendName])


getGlyphNamesTestData = [
    ("rcjk", 80, ["DC_0030_00", "DC_0031_00", "DC_0032_00", "DC_0033_00"]),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "backendName, numGlyphs, firstFourGlyphNames", getGlyphNamesTestData
)
async def test_getGlyphNames(backendName, numGlyphs, firstFourGlyphNames):
    font = getTestFont(backendName)
    with contextlib.closing(font):
        glyphNames = sorted(await font.getGlyphMap())
        assert numGlyphs == len(glyphNames)
        assert firstFourGlyphNames == sorted(glyphNames)[:4]


getGlyphMapTestData = [
    ("rcjk", 80, {"uni0031": [ord("1")]}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("backendName, numGlyphs, testMapping", getGlyphMapTestData)
async def test_getGlyphMap(backendName, numGlyphs, testMapping):
    font = getTestFont(backendName)
    with contextlib.closing(font):
        revCmap = await font.getGlyphMap()
        assert numGlyphs == len(revCmap)
        for glyphName, unicodes in testMapping.items():
            assert revCmap[glyphName] == unicodes


@pytest.mark.asyncio
@pytest.mark.parametrize("backendName, expectedGlyph", getGlyphTestData)
async def test_getGlyph(backendName, expectedGlyph):
    expectedGlyph = from_dict(VariableGlyph, expectedGlyph)
    font = getTestFont(backendName)
    with contextlib.closing(font):
        glyph = await font.getGlyph(expectedGlyph.name)
        assert asdict(glyph) == asdict(expectedGlyph)
        assert glyph == expectedGlyph


getGlobalAxesTestData = [
    (
        "rcjk",
        [
            {
                "defaultValue": 400,
                "maxValue": 700,
                "minValue": 400,
                "label": "Weight",
                "name": "wght",
            },
        ],
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("backendName, expectedGlobalAxes", getGlobalAxesTestData)
async def test_getGlobalAxes(backendName, expectedGlobalAxes):
    font = getTestFont(backendName)
    globalAxes = await font.getGlobalAxes()
    assert expectedGlobalAxes == globalAxes


@pytest.mark.asyncio
@pytest.mark.parametrize("backendName, expectedLibLen", [("rcjk", 4)])
async def test_getFontLib(backendName, expectedLibLen):
    font = getTestFont(backendName)
    lib = await font.getFontLib()
    assert expectedLibLen == len(lib)


@pytest.mark.asyncio
@pytest.mark.parametrize("backendName, expectedUnitsPerEm", [("rcjk", 1000)])
async def test_getUnitsPerEm(backendName, expectedUnitsPerEm):
    font = getTestFont(backendName)
    unitsPerEm = await font.getUnitsPerEm()
    assert expectedUnitsPerEm == unitsPerEm
