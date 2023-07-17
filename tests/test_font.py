import contextlib
import pathlib
import shutil
from dataclasses import asdict
from importlib.metadata import entry_points

import pytest
from fontra.core.classes import (
    GlobalAxis,
    Layer,
    LocalAxis,
    PackedPath,
    Source,
    StaticGlyph,
    VariableGlyph,
    from_dict,
)

from fontra_rcjk.base import makeSafeLayerName

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
                    "customData": {"fontra.development.status": 0},
                },
                {
                    "name": "longbar",
                    "location": {"HLON": 1.0},
                    "layerName": "longbar",
                    "customData": {"fontra.development.status": 0},
                },
                {
                    "name": "bold",
                    "location": {"WGHT": 1.0},
                    "layerName": "bold",
                    "customData": {"fontra.development.status": 0},
                },
            ],
            "layers": {
                "foreground": {
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
                "bold": {
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
                "longbar": {
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
            },
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
                    "customData": {"fontra.development.status": 0},
                },
                {
                    "name": "wght",
                    "location": {"wght": 1.0},
                    "layerName": "wght",
                    "customData": {"fontra.development.status": 0},
                },
            ],
            "layers": {
                "foreground": {
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
                "wght": {
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
            },
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
                    "customData": {"fontra.development.status": 0},
                },
                {
                    "name": "X_X_bo",
                    "location": {"X_X_bo": 1.0},
                    "layerName": "X_X_bo_1_layer",
                    "customData": {"fontra.development.status": 0},
                },
                {
                    "name": "X_X_la",
                    "location": {"X_X_la": 1.0},
                    "layerName": "X_X_la_2_layer",
                    "customData": {"fontra.development.status": 0},
                },
            ],
            "layers": {
                "foreground": {
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
                "X_X_bo_1_layer": {
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
                "X_X_la_2_layer": {
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
            },
        },
    ),
]


testFontPaths = {
    "rcjk": dataDir / "figArnaud.rcjk",
}


def getBackendClassByName(backendName):
    backendEntryPoints = entry_points(group="fontra.filesystem.backends")
    return backendEntryPoints[backendName].load()


def getTestFont(backendName):
    cls = getBackendClassByName(backendName)
    return cls.fromPath(testFontPaths[backendName])


getGlyphNamesTestData = [
    ("rcjk", 81, ["DC_0030_00", "DC_0031_00", "DC_0032_00", "DC_0033_00"]),
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
    ("rcjk", 81, {"uni0031": [ord("1")]}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("backendName, numGlyphs, testMapping", getGlyphMapTestData)
async def test_getGlyphMap(backendName, numGlyphs, testMapping):
    font = getTestFont(backendName)
    with contextlib.closing(font):
        glyphMap = await font.getGlyphMap()
        assert numGlyphs == len(glyphMap)
        for glyphName, unicodes in testMapping.items():
            assert glyphMap[glyphName] == unicodes


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
            GlobalAxis(
                label="Weight",
                name="wght",
                tag="wght",
                minValue=400,
                defaultValue=400,
                maxValue=700,
            ),
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
@pytest.mark.parametrize("backendName, expectedLibLen", [("rcjk", 5)])
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


@pytest.fixture
def writableTestFont(tmpdir):
    sourcePath = testFontPaths["rcjk"]
    destPath = tmpdir / sourcePath.name
    shutil.copytree(sourcePath, destPath)
    return getBackendClassByName("rcjk").fromPath(destPath)


glyphData_a_before = [
    "<?xml version='1.0' encoding='UTF-8'?>",
    '<glyph name="a" format="2">',
    '  <advance width="500"/>',
    '  <unicode hex="0061"/>',
    "  <note>",
    "some note",
    "</note>",
    '  <guideline x="360" y="612" angle="0"/>',
    "  <outline>",
    "    <contour>",
    '      <point x="50" y="0" type="line"/>',
    '      <point x="250" y="650" type="line"/>',
    '      <point x="450" y="0" type="line"/>',
    "    </contour>",
    "  </outline>",
    "  <lib>",
    "    <dict>",
    "      <key>robocjk.status</key>",
    "      <integer>0</integer>",
    "      <key>robocjk.variationGlyphs</key>",
    "      <array>",
    "        <dict>",
    "          <key>layerName</key>",
    "          <string>bold</string>",
    "          <key>location</key>",
    "          <dict>",
    "            <key>wght</key>",
    "            <integer>700</integer>",
    "          </dict>",
    "          <key>on</key>",
    "          <true/>",
    "          <key>sourceName</key>",
    "          <string>bold</string>",
    "          <key>status</key>",
    "          <integer>0</integer>",
    "        </dict>",
    "      </array>",
    "      <key>xyz.fontra.something.nothing</key>",
    "      <string>test</string>",
    "    </dict>",
    "  </lib>",
    "</glyph>",
]

glyphData_a_after = [
    "<?xml version='1.0' encoding='UTF-8'?>",
    '<glyph name="a" format="2">',
    '  <advance width="500"/>',
    '  <unicode hex="0061"/>',
    "  <note>",
    "some note",
    "</note>",
    '  <guideline x="360" y="612" angle="0"/>',
    "  <outline>",
    "    <contour>",
    '      <point x="80" y="100" type="line"/>',
    '      <point x="250" y="650" type="line"/>',
    '      <point x="450" y="0" type="line"/>',
    "    </contour>",
    "  </outline>",
    "  <lib>",
    "    <dict>",
    "      <key>robocjk.status</key>",
    "      <integer>0</integer>",
    "      <key>robocjk.variationGlyphs</key>",
    "      <array>",
    "        <dict>",
    "          <key>layerName</key>",
    "          <string>bold</string>",
    "          <key>location</key>",
    "          <dict>",
    "            <key>wght</key>",
    "            <integer>700</integer>",
    "          </dict>",
    "          <key>on</key>",
    "          <true/>",
    "          <key>sourceName</key>",
    "          <string>bold</string>",
    "          <key>status</key>",
    "          <integer>0</integer>",
    "        </dict>",
    "      </array>",
    "      <key>xyz.fontra.something.nothing</key>",
    "      <string>test</string>",
    "    </dict>",
    "  </lib>",
    "</glyph>",
]


async def test_putGlyph(writableTestFont):
    with contextlib.closing(writableTestFont):
        glyphMap = await writableTestFont.getGlyphMap()
        glyph = await writableTestFont.getGlyph("a")
        assert len(glyph.axes) == 0
        assert len(glyph.sources) == 2
        assert len(glyph.layers) == 2
        glifPath = writableTestFont.path / "characterGlyph" / "a.glif"
        glifData_before = glifPath.read_text().splitlines()
        assert glifData_before == glyphData_a_before

        coords = glyph.layers["foreground"].glyph.path.coordinates
        coords[0] = 80
        coords[1] = 100
        await writableTestFont.putGlyph(glyph.name, glyph, glyphMap["a"])
        glifData_after = glifPath.read_text().splitlines()
        assert glifData_after == glyphData_a_after


glyphData_a_after_delete_source = [
    "<?xml version='1.0' encoding='UTF-8'?>",
    '<glyph name="a" format="2">',
    '  <advance width="500"/>',
    '  <unicode hex="0061"/>',
    "  <note>",
    "some note",
    "</note>",
    '  <guideline x="360" y="612" angle="0"/>',
    "  <outline>",
    "    <contour>",
    '      <point x="50" y="0" type="line"/>',
    '      <point x="250" y="650" type="line"/>',
    '      <point x="450" y="0" type="line"/>',
    "    </contour>",
    "  </outline>",
    "  <lib>",
    "    <dict>",
    "      <key>robocjk.status</key>",
    "      <integer>0</integer>",
    "      <key>xyz.fontra.something.nothing</key>",
    "      <string>test</string>",
    "    </dict>",
    "  </lib>",
    "</glyph>",
]


async def test_delete_source_layer(writableTestFont):
    with contextlib.closing(writableTestFont):
        glifPathBold = writableTestFont.path / "characterGlyph" / "bold" / "a.glif"
        assert glifPathBold.exists()

        glyphMap = await writableTestFont.getGlyphMap()
        glyph = await writableTestFont.getGlyph("a")
        del glyph.sources[1]
        del glyph.layers["bold"]

        await writableTestFont.putGlyph(glyph.name, glyph, glyphMap["a"])

        glifPath = writableTestFont.path / "characterGlyph" / "a.glif"
        glifData = glifPath.read_text().splitlines()
        assert glifData == glyphData_a_after_delete_source
        assert not glifPathBold.exists()


newGlyphTestData = [
    "<?xml version='1.0' encoding='UTF-8'?>",
    '<glyph name="b" format="2">',
    '  <unicode hex="0062"/>',
    "  <outline>",
    "    <contour>",
    '      <point x="0" y="0" type="line"/>',
    "    </contour>",
    "  </outline>",
    "  <lib>",
    "    <dict>",
    "      <key>robocjk.axes</key>",
    "      <array>",
    "        <dict>",
    "          <key>defaultValue</key>",
    "          <integer>400</integer>",
    "          <key>maxValue</key>",
    "          <integer>700</integer>",
    "          <key>minValue</key>",
    "          <integer>100</integer>",
    "          <key>name</key>",
    "          <string>wght</string>",
    "        </dict>",
    "      </array>",
    "      <key>robocjk.status</key>",
    "      <integer>0</integer>",
    "      <key>robocjk.variationGlyphs</key>",
    "      <array>",
    "        <dict>",
    "          <key>layerName</key>",
    "          <string>bold</string>",
    "          <key>location</key>",
    "          <dict/>",
    "          <key>on</key>",
    "          <true/>",
    "          <key>sourceName</key>",
    "          <string>bold</string>",
    "          <key>status</key>",
    "          <integer>0</integer>",
    "        </dict>",
    "      </array>",
    "    </dict>",
    "  </lib>",
    "</glyph>",
]


def makeTestPath():
    return PackedPath.fromUnpackedContours(
        [{"points": [{"x": 0, "y": 0}], "isClosed": True}]
    )


async def test_new_glyph(writableTestFont):
    with contextlib.closing(writableTestFont):
        glyph = VariableGlyph(
            name="b",
            axes=[LocalAxis(name="wght", minValue=100, defaultValue=400, maxValue=700)],
            sources=[
                Source(name="default", layerName="default"),
                Source(name="bold", layerName="bold"),
            ],
            layers={
                "default": Layer(glyph=StaticGlyph(path=makeTestPath())),
                "bold": Layer(glyph=StaticGlyph(path=makeTestPath())),
            },
        )
        await writableTestFont.putGlyph(glyph.name, glyph, [ord("b")])

        glifPath = writableTestFont.path / "characterGlyph" / "b.glif"
        glifData = glifPath.read_text().splitlines()
        assert glifData == newGlyphTestData


async def test_add_new_layer(writableTestFont):
    with contextlib.closing(writableTestFont):
        glyphName = "a"
        glyphMap = await writableTestFont.getGlyphMap()
        glyph = await writableTestFont.getGlyph(glyphName)
        newLayerName = "new_layer_name"

        layerPath = writableTestFont.path / "characterGlyph" / newLayerName
        assert not layerPath.exists()

        glyph.sources.append(Source(name=newLayerName, layerName=newLayerName))
        glyph.layers[newLayerName] = Layer(
            glyph=StaticGlyph(xAdvance=500, path=makeTestPath())
        )

        await writableTestFont.putGlyph(glyph.name, glyph, glyphMap[glyphName])

        assert layerPath.exists()
        layerGlifPath = layerPath / f"{glyphName}.glif"
        assert layerGlifPath.exists()


@pytest.mark.parametrize("glyphName", ["a", "uni0030"])
async def test_write_roundtrip(writableTestFont, glyphName):
    with contextlib.closing(writableTestFont):
        glyphMap = await writableTestFont.getGlyphMap()
        glyph = await writableTestFont.getGlyph(glyphName)

        layerGlifPath = writableTestFont.path / "characterGlyph" / f"{glyphName}.glif"

        existingLayerData = layerGlifPath.read_text()
        await writableTestFont.putGlyph(glyph.name, glyph, glyphMap[glyphName])
        # Write the glyph again to ensure a write bug that would duplicate the
        # components doesn't resurface
        await writableTestFont.putGlyph(glyph.name, glyph, glyphMap[glyphName])
        newLayerData = layerGlifPath.read_text()

        assert existingLayerData == newLayerData


layerNameMappingTestData = [
    "<?xml version='1.0' encoding='UTF-8'?>",
    '<glyph name="a" format="2">',
    '  <advance width="500"/>',
    '  <unicode hex="0061"/>',
    "  <note>",
    "some note",
    "</note>",
    '  <guideline x="360" y="612" angle="0"/>',
    "  <outline>",
    "    <contour>",
    '      <point x="50" y="0" type="line"/>',
    '      <point x="250" y="650" type="line"/>',
    '      <point x="450" y="0" type="line"/>',
    "    </contour>",
    "  </outline>",
    "  <lib>",
    "    <dict>",
    "      <key>fontra.layerNames</key>",
    "      <dict>",
    "        <key>boooo_oooold.75e003ed2da2</key>",
    "        <string>boooo/oooold</string>",
    "        <key>boooo_ooooldboooo_ooooldboooo_ooooldb.360a3fdd78e6</key>",
    "        <string>boooo/ooooldboooo/ooooldboooo/ooooldboooo/ooooldboooo/oooold</string>",
    "      </dict>",
    "      <key>robocjk.status</key>",
    "      <integer>0</integer>",
    "      <key>robocjk.variationGlyphs</key>",
    "      <array>",
    "        <dict>",
    "          <key>layerName</key>",
    "          <string>bold</string>",
    "          <key>location</key>",
    "          <dict>",
    "            <key>wght</key>",
    "            <integer>700</integer>",
    "          </dict>",
    "          <key>on</key>",
    "          <true/>",
    "          <key>sourceName</key>",
    "          <string>bold</string>",
    "          <key>status</key>",
    "          <integer>0</integer>",
    "        </dict>",
    "        <dict>",
    "          <key>layerName</key>",
    "          <string>boooo_oooold.75e003ed2da2</string>",
    "          <key>location</key>",
    "          <dict/>",
    "          <key>on</key>",
    "          <true/>",
    "          <key>sourceName</key>",
    "          <string>boooo/oooold</string>",
    "          <key>status</key>",
    "          <integer>0</integer>",
    "        </dict>",
    "        <dict>",
    "          <key>layerName</key>",
    "          <string>boooo_ooooldboooo_ooooldboooo_ooooldb.360a3fdd78e6</string>",
    "          <key>location</key>",
    "          <dict/>",
    "          <key>on</key>",
    "          <true/>",
    "          <key>sourceName</key>",
    "          <string>boooo/ooooldboooo/ooooldboooo/ooooldboooo/ooooldboooo/oooold</string>",
    "          <key>status</key>",
    "          <integer>0</integer>",
    "        </dict>",
    "      </array>",
    "      <key>xyz.fontra.something.nothing</key>",
    "      <string>test</string>",
    "    </dict>",
    "  </lib>",
    "</glyph>",
]


async def test_bad_layer_name(writableTestFont):
    with contextlib.closing(writableTestFont):
        glyphName = "a"
        glyphMap = await writableTestFont.getGlyphMap()
        glyph = await writableTestFont.getGlyph(glyphName)

        for badLayerName in ["boooo/oooold", "boooo/oooold" * 5]:
            safeLayerName = makeSafeLayerName(badLayerName)

            layerPath = writableTestFont.path / "characterGlyph" / safeLayerName
            assert not layerPath.exists()

            glyph.sources.append(Source(name=badLayerName, layerName=badLayerName))
            glyph.layers[badLayerName] = Layer(
                glyph=StaticGlyph(xAdvance=500, path=makeTestPath())
            )

        await writableTestFont.putGlyph(glyph.name, glyph, glyphMap[glyphName])

        assert layerPath.exists()
        layerGlifPath = layerPath / f"{glyphName}.glif"
        assert layerGlifPath.exists()

        mainGlifPath = writableTestFont.path / "characterGlyph" / f"{glyphName}.glif"
        glifData = mainGlifPath.read_text()
        assert glifData.splitlines() == layerNameMappingTestData


deleteItemsTestData = [
    "<?xml version='1.0' encoding='UTF-8'?>",
    '<glyph name="uni0030" format="2">',
    '  <advance width="600"/>',
    '  <unicode hex="0030"/>',
    '  <guideline x="360" y="612" angle="0" identifier="gRMeb2PVEQ"/>',
    '  <guideline x="307" y="600" angle="0" identifier="386e1cIMnm"/>',
    '  <guideline x="305" y="-12" angle="0" identifier="xMdDy12pWP"/>',
    "  <outline>",
    "  </outline>",
    "  <lib>",
    "    <dict>",
    "      <key>public.markColor</key>",
    "      <string>1,0,0,1</string>",
    "      <key>robocjk.status</key>",
    "      <integer>0</integer>",
    "      <key>xyz.fontra.test</key>",
    "      <string>test</string>",
    "    </dict>",
    "  </lib>",
    "</glyph>",
]


async def test_delete_items(writableTestFont):
    with contextlib.closing(writableTestFont):
        glyphName = "uni0030"
        glyphMap = await writableTestFont.getGlyphMap()
        glyph = await writableTestFont.getGlyph(glyphName)

        glyph.axes = []
        glyph.sources = [glyph.sources[0]]
        layerName = glyph.sources[0].layerName
        layer = glyph.layers[layerName]
        layer.glyph.components = []
        glyph.layers = {layerName: layer}

        await writableTestFont.putGlyph(glyph.name, glyph, glyphMap[glyphName])

        mainGlifPath = writableTestFont.path / "characterGlyph" / f"{glyphName}.glif"
        glifData = mainGlifPath.read_text()
        assert glifData.splitlines() == deleteItemsTestData


expectedReadMixedComponentTestData = {
    "name": "b",
    "axes": [],
    "sources": [
        {
            "name": "<default>",
            "layerName": "foreground",
            "location": {},
            "inactive": False,
            "customData": {"fontra.development.status": 0},
        }
    ],
    "layers": {
        "foreground": {
            "glyph": {
                "path": {"coordinates": [], "pointTypes": [], "contourInfo": []},
                "components": [
                    {
                        "name": "a",
                        "transformation": {
                            "translateX": 0,
                            "translateY": 0,
                            "rotation": 0.0,
                            "scaleX": 1.0,
                            "scaleY": 1.0,
                            "skewX": 0.0,
                            "skewY": 0.0,
                            "tCenterX": 0,
                            "tCenterY": 0,
                        },
                        "location": {},
                    },
                    {
                        "name": "DC_0033_00",
                        "transformation": {
                            "translateX": 30,
                            "translateY": 0,
                            "rotation": 0,
                            "scaleX": 1,
                            "scaleY": 1,
                            "skewX": 0,
                            "skewY": 0,
                            "tCenterX": 0,
                            "tCenterY": 0,
                        },
                        "location": {"X_X_bo": 0, "X_X_la": 0},
                    },
                ],
                "xAdvance": 500,
                "yAdvance": None,
                "verticalOrigin": None,
            },
            "customData": {},
        }
    },
    "customData": {},
}


async def test_readMixClassicAndVariableComponents():
    font = getTestFont("rcjk")
    with contextlib.closing(font):
        glyph = await font.getGlyph("b")
        assert expectedReadMixedComponentTestData == asdict(glyph)


expectedWriteMixedComponentTestData = [
    "<?xml version='1.0' encoding='UTF-8'?>",
    '<glyph name="b" format="2">',
    '  <advance width="500"/>',
    '  <unicode hex="0062"/>',
    "  <outline>",
    "  </outline>",
    "  <lib>",
    "    <dict>",
    "      <key>robocjk.deepComponents</key>",
    "      <array>",
    "        <dict>",
    "          <key>coord</key>",
    "          <dict/>",
    "          <key>name</key>",
    "          <string>a</string>",
    "          <key>transform</key>",
    "          <dict>",
    "            <key>rotation</key>",
    "            <real>0.0</real>",
    "            <key>scalex</key>",
    "            <real>1.0</real>",
    "            <key>scaley</key>",
    "            <real>1.0</real>",
    "            <key>tcenterx</key>",
    "            <integer>0</integer>",
    "            <key>tcentery</key>",
    "            <integer>0</integer>",
    "            <key>x</key>",
    "            <integer>0</integer>",
    "            <key>y</key>",
    "            <integer>0</integer>",
    "          </dict>",
    "        </dict>",
    "        <dict>",
    "          <key>coord</key>",
    "          <dict>",
    "            <key>X_X_bo</key>",
    "            <integer>0</integer>",
    "            <key>X_X_la</key>",
    "            <integer>0</integer>",
    "          </dict>",
    "          <key>name</key>",
    "          <string>DC_0033_00</string>",
    "          <key>transform</key>",
    "          <dict>",
    "            <key>rotation</key>",
    "            <integer>0</integer>",
    "            <key>scalex</key>",
    "            <integer>1</integer>",
    "            <key>scaley</key>",
    "            <integer>1</integer>",
    "            <key>tcenterx</key>",
    "            <integer>0</integer>",
    "            <key>tcentery</key>",
    "            <integer>0</integer>",
    "            <key>x</key>",
    "            <integer>30</integer>",
    "            <key>y</key>",
    "            <integer>0</integer>",
    "          </dict>",
    "        </dict>",
    "      </array>",
    "      <key>robocjk.status</key>",
    "      <integer>0</integer>",
    "    </dict>",
    "  </lib>",
    "</glyph>",
]


async def test_writeMixClassicAndVariableComponents(writableTestFont):
    with contextlib.closing(writableTestFont):
        glyphMap = await writableTestFont.getGlyphMap()
        glyph = await writableTestFont.getGlyph("b")
        await writableTestFont.putGlyph("b", glyph, glyphMap["b"])
        mainGlifPath = writableTestFont.path / "characterGlyph" / "b.glif"
        glifData = mainGlifPath.read_text()
        assert expectedWriteMixedComponentTestData == glifData.splitlines()
