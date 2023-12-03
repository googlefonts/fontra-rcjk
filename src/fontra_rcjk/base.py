import asyncio
import hashlib
from copy import deepcopy
from dataclasses import asdict
from functools import cached_property
from typing import Union

from fontra.backends.designspace import cleanupTransform
from fontra.core.classes import (
    Component,
    GlobalAxis,
    GlobalDiscreteAxis,
    Layer,
    LocalAxis,
    Source,
    StaticGlyph,
    VariableGlyph,
    structure,
)
from fontra.core.path import PackedPathPointPen
from fontTools.misc.transform import DecomposedTransform
from fontTools.ufoLib.filenames import illegalCharacters
from fontTools.ufoLib.glifLib import readGlyphFromString, writeGlyphToString

FONTRA_STATUS_KEY = "fontra.development.status"


class GLIFGlyph:
    def __init__(self):
        self.name = None  # Must be set to a string before we can write GLIF data
        self.unicodes = []
        self.width = 0
        self.path = None
        self.lib = {}
        self.components = []
        self.variableComponents = []

    @classmethod
    def fromGLIFData(cls, glifData):
        self = cls()
        pen = PackedPathPointPen()
        readGlyphFromString(glifData, self, pen, validate=False)
        self.path = pen.getPath()
        self.components = pen.components
        return self

    @classmethod
    def fromStaticGlyph(cls, glyphName, staticGlyph, allowClassicComponents=False):
        self = cls()
        self.updateFromStaticGlyph(glyphName, staticGlyph, allowClassicComponents)
        return self

    def updateFromStaticGlyph(
        self, glyphName, staticGlyph, allowClassicComponents=False
    ):
        self.name = glyphName
        self.width = staticGlyph.xAdvance
        self.path = staticGlyph.path
        self.components = []
        self.variableComponents = []
        for component in staticGlyph.components:
            if component.location or not allowClassicComponents:
                self.variableComponents.append(component)
            else:
                # classic component
                self.components.append(component)

    def asGLIFData(self):
        return writeGlyphToString(self.name, self, self.drawPoints, validate=False)

    def hasOutlineOrClassicComponents(self):
        return (
            True
            if (self.path is not None and self.path.coordinates) or self.components
            else False
        )

    def drawPoints(self, pen):
        if self.path is not None:
            self.path.drawPoints(pen)
        for component in self.components:
            pen.addComponent(
                component.name,
                cleanupTransform(component.transformation.toTransform()),
            )

    @cached_property
    def axes(self):
        return [cleanupAxis(axis) for axis in self.lib.get("robocjk.axes", ())]

    def getComponentNames(self):
        classicComponentNames = {compo.name for compo in self.components}
        deepComponentNames = {
            compo["name"] for compo in self.lib.get("robocjk.deepComponents", ())
        }
        return sorted(classicComponentNames | deepComponentNames)

    def toStaticGlyph(self):
        return StaticGlyph(
            xAdvance=self.width,
            path=deepcopy(self.path),
            components=deepcopy(self.components),
        )

    def copy(self):
        return deepcopy(self)


def cleanupAxis(axisDict):
    axisDict = dict(axisDict)
    minValue = axisDict["minValue"]
    maxValue = axisDict["maxValue"]
    defaultValue = axisDict.get("defaultValue", minValue)
    minValue, maxValue = sorted([minValue, maxValue])
    axisDict["minValue"] = minValue
    axisDict["defaultValue"] = defaultValue
    axisDict["maxValue"] = maxValue
    return LocalAxis(**axisDict)


def buildVariableGlyphFromLayerGlyphs(layerGlyphs):
    layers = {
        layerName: Layer(glyph=glyph.toStaticGlyph())
        for layerName, glyph in layerGlyphs.items()
    }

    defaultGlyph = layerGlyphs["foreground"]
    defaultComponents = buildVariableComponentsFromLibComponents(
        defaultGlyph.lib.get("robocjk.deepComponents", ()), None
    )
    if defaultComponents:
        layers["foreground"].glyph.components += defaultComponents

    fontraLayerNameMapping = dict(defaultGlyph.lib.get("fontra.layerNames", {}))

    dcNames = [c.name for c in defaultComponents]

    sources = [
        Source(
            name="<default>",
            layerName="foreground",
            customData={FONTRA_STATUS_KEY: defaultGlyph.lib.get("robocjk.status", 0)},
        )
    ]
    variationGlyphData = defaultGlyph.lib.get("robocjk.variationGlyphs", ())

    activeLayerNames = set()
    for varDict in variationGlyphData:
        layerName = varDict.get("layerName")
        if layerName:
            activeLayerNames.add(layerName)

    # Only glyphs with outlines (or classic components) have "layers", in the rcjk
    # sense of the word, but Fontra always needs unique layer names, as it doesn't
    # make the distinction. So we keep a set of made up names, so we can ensure
    # we create no duplicates.
    syntheticLayerNames = set()

    for sourceIndex, varDict in enumerate(variationGlyphData, 1):
        inactiveFlag = not varDict.get("on", True)
        layerName = varDict.get("layerName")
        sourceName = varDict.get("sourceName")
        if not sourceName:
            sourceName = layerName if layerName else f"source_{sourceIndex}"
        if not layerName:
            layerName = sourceName
            counter = 1
            while layerName in syntheticLayerNames:
                layerName = f"{sourceName}#{counter}"
                counter += 1
            assert layerName not in activeLayerNames, layerName
            # layerName should not exist in layers, and if it does,
            # it must be a zombie layer that should have been deleted.
            # We'll delete it to make sure we don't reuse its data
            layers.pop(layerName, None)

        fontraLayerNameMapping[layerName] = varDict.get(
            "fontraLayerName"
        ) or fontraLayerNameMapping.get(layerName, layerName)

        syntheticLayerNames.add(layerName)

        xAdvance = defaultGlyph.width
        if layerName in layers:
            layerGlyph = layers[layerName].glyph
            xAdvance = layerGlyphs[layerName].width
        else:
            layerGlyph = StaticGlyph()
            layers[layerName] = Layer(glyph=layerGlyph)

        if "width" in varDict:
            xAdvance = varDict["width"]
        layerGlyph.xAdvance = xAdvance

        components = buildVariableComponentsFromLibComponents(
            varDict.get("deepComponents", ()), dcNames
        )
        if components:
            layerGlyph.components += components

        location = varDict["location"]
        sources.append(
            Source(
                name=sourceName,
                location=location,
                layerName=fontraLayerNameMapping.get(layerName, layerName),
                inactive=inactiveFlag,
                customData={FONTRA_STATUS_KEY: varDict.get("status", 0)},
            )
        )

    if fontraLayerNameMapping:
        layers = {
            fontraLayerNameMapping.get(layerName, layerName): layer
            for layerName, layer in layers.items()
        }

    return VariableGlyph(
        name=defaultGlyph.name,
        axes=defaultGlyph.axes,
        sources=sources,
        layers=layers,
    )


def buildVariableComponentsFromLibComponents(deepComponents, dcNames):
    components = []
    for index, deepCompoDict in enumerate(deepComponents):
        impliedName = (
            dcNames[index]
            if dcNames and index < len(dcNames)
            else f"ComponentNotFound#{index}"
        )
        name = deepCompoDict["name"] if "name" in deepCompoDict else impliedName
        component = Component(name=name)
        if deepCompoDict["coord"]:
            component.location = dict(deepCompoDict["coord"])
        component.transformation = convertTransformation(deepCompoDict["transform"])
        components.append(component)
    return components


def convertTransformation(rcjkTransformation):
    t = rcjkTransformation
    return DecomposedTransform(
        translateX=t["x"],
        translateY=t["y"],
        rotation=t["rotation"],
        scaleX=t["scalex"],
        scaleY=t["scaley"],
        tCenterX=t["tcenterx"],
        tCenterY=t["tcentery"],
    )


def buildLayerGlyphsFromVariableGlyph(
    glyphName, glyph, unicodes, defaultLocation, existingLayerGlyphs
):
    fontraLayerNameMapping = {}
    defaultLayerName = None
    for source in glyph.sources:
        location = {**defaultLocation, **source.location}
        if location == defaultLocation:
            defaultLayerName = source.layerName
            break
    if defaultLayerName is None:
        # TODO: better exception
        raise AssertionError("no default source/layer found")

    layerGlyphs = {}
    for layerName, layer in glyph.layers.items():
        if layerName == defaultLayerName:
            layerName = "foreground"
        assert layerName not in layerGlyphs
        layerGlyph = existingLayerGlyphs.get(layerName)
        if layerGlyph is None:
            layerGlyph = GLIFGlyph()
        else:
            layerGlyph = layerGlyph.copy()
        layerGlyph.updateFromStaticGlyph(glyphName, layer.glyph)

        safeLayerName = makeSafeLayerName(layerName)
        if safeLayerName != layerName:
            fontraLayerNameMapping[safeLayerName] = layerName

        layerGlyphs[layerName] = layerGlyph
        layerGlyphs[layerName].unicodes = unicodes
    defaultGlyph = layerGlyphs["foreground"]

    if glyph.axes:
        defaultGlyph.lib["robocjk.axes"] = [asdict(axis) for axis in glyph.axes]
    else:
        defaultGlyph.lib.pop("robocjk.axes", None)

    deepComponents = buildLibComponentsFromVariableComponents(
        defaultGlyph.variableComponents
    )
    if deepComponents:
        defaultGlyph.lib["robocjk.deepComponents"] = deepComponents
    else:
        defaultGlyph.lib.pop("robocjk.deepComponents", None)

    variationGlyphs = []
    for source in glyph.sources:
        devStatus = source.customData.get(FONTRA_STATUS_KEY, 0)
        if source.layerName == defaultLayerName:
            defaultGlyph.lib["robocjk.status"] = devStatus
            # This is the default glyph, we don't treat it like a layer in .rcjk
            continue

        layerGlyph = layerGlyphs[source.layerName]
        varDict = {
            "sourceName": source.name,
            "on": not source.inactive,
            "location": source.location,
            "status": devStatus,
        }
        if layerGlyph.width != defaultGlyph.width:
            varDict["width"] = layerGlyph.width

        deepComponents = buildLibComponentsFromVariableComponents(
            layerGlyph.variableComponents
        )
        if deepComponents:
            varDict["deepComponents"] = deepComponents

        if layerGlyph.hasOutlineOrClassicComponents():
            safeLayerName = makeSafeLayerName(source.layerName)
            varDict["layerName"] = safeLayerName
            if safeLayerName != source.layerName:
                fontraLayerNameMapping[safeLayerName] = source.layerName
                varDict["fontraLayerName"] = source.layerName
        else:
            varDict["layerName"] = ""  # Mimic RoboCJK
            if source.layerName != source.name:
                varDict["fontraLayerName"] = source.layerName
            # This is a "virtual" layer: all info will go to defaultGlyph.lib,
            # and no "true" layer will be written
            del layerGlyphs[source.layerName]

        variationGlyphs.append(varDict)

    if variationGlyphs:
        defaultGlyph.lib["robocjk.variationGlyphs"] = variationGlyphs
    else:
        defaultGlyph.lib.pop("robocjk.variationGlyphs", None)

    if fontraLayerNameMapping:
        rcjkLayerNameMapping = {v: k for k, v in fontraLayerNameMapping.items()}
        layerGlyphs = {
            rcjkLayerNameMapping.get(layerName, layerName): layerGlyph
            for layerName, layerGlyph in layerGlyphs.items()
        }

    # Get rid of legacy data
    defaultGlyph.lib.pop("fontra.layerNames", None)

    return layerGlyphs


def buildLibComponentsFromVariableComponents(variableComponents):
    components = []
    for compo in variableComponents:
        compoDict = dict(name=compo.name)
        compoDict.update(
            coord=compo.location,
            transform=unconvertTransformation(compo.transformation),
        )
        components.append(compoDict)
    return components


EPSILON = 1e-9


def unconvertTransformation(transformation):
    if abs(transformation.skewX) > EPSILON or abs(transformation.skewY) > EPSILON:
        raise TypeError("rcjk does not support skewing of variable components")
    t = transformation
    return dict(
        x=t.translateX,
        y=t.translateY,
        rotation=t.rotation,
        scalex=t.scaleX,
        scaley=t.scaleY,
        tcenterx=t.tCenterX,
        tcentery=t.tCenterY,
    )


# def cleanupIntFloatValuesInDict(d):
#     return {k: int(v) if int(v) == v else v for k, v in d.items()}


class TimedCache:
    def __init__(self, timeOut=5):
        self.cacheDict = {}
        self.timeOut = timeOut
        self.timerTask = None

    def get(self, key, default=None):
        return self.cacheDict.get(key, default)

    def __getitem__(self, key):
        return self.cacheDict[key]

    def __setitem__(self, key, value):
        self.cacheDict[key] = value

    def __contains__(self, key):
        return key in self.cacheDict

    def clear(self):
        self.cacheDict.clear()

    def updateTimeOut(self):
        if self.timerTask is not None:
            self.timerTask.cancel()

        async def clearCacheDict():
            await asyncio.sleep(self.timeOut)
            self.clear()

        self.timerTask = asyncio.create_task(clearCacheDict())

    def cancel(self):
        if self.timerTask is not None:
            self.timerTask.cancel()


illegalCharactersMap = {ord(c): ord("_") for c in illegalCharacters}
hexHashLength = 12
maxLayerNameLength = 50  # For django-rcjk
maxLayerNameLengthWithoutHash = maxLayerNameLength - 1 - hexHashLength


def makeSafeLayerName(layerName):
    """Make a layer name that is safe to use as a file name on the file system,
    and as a layer name for django-rcjk, which has a 50 character limit, and
    additionally will also use it as a file system name upon export.
    """
    safeLayerName = layerName.translate(illegalCharactersMap)
    safeLayerName = safeLayerName[:maxLayerNameLength]
    if safeLayerName != layerName:
        layerNameHash = hashlib.sha256(layerName.encode("utf-8")).hexdigest()[
            :hexHashLength
        ]
        safeLayerName = (
            f"{safeLayerName[:maxLayerNameLengthWithoutHash]}.{layerNameHash}"
        )
    assert len(safeLayerName) <= maxLayerNameLength
    return safeLayerName


standardCustomDataItems = {
    "fontra.sourceStatusFieldDefinitions": [
        {
            "label": "In progress",
            "color": (1.0, 0.0, 0.0, 1.0),
            "value": 0,
            "isDefault": True,
        },
        {
            "label": "Checking-1",
            "color": (1.0, 0.5, 0.0, 1.0),
            "value": 1,
        },
        {
            "label": "Checking-2",
            "color": (1.0, 1.0, 0.0, 1.0),
            "value": 2,
        },
        {
            "label": "Checking-3",
            "color": (0.0, 0.5, 1.0, 1.0),
            "value": 3,
        },
        {
            "label": "Validated",
            "color": (0.0, 1.0, 0.5, 1.0),
            "value": 4,
        },
    ]
}


def unpackAxes(dsAxes):
    return [_unpackDSAxis(axis) for axis in dsAxes]


def _unpackDSAxis(dsAxis):
    if "label" in dsAxis:
        return structure(dsAxis, Union[GlobalAxis, GlobalDiscreteAxis])
    # Legacy rcjk ds data
    return GlobalAxis(
        label=dsAxis["name"],
        name=dsAxis["tag"],
        tag=dsAxis["tag"],
        minValue=dsAxis["minValue"],
        defaultValue=dsAxis["defaultValue"],
        maxValue=dsAxis["maxValue"],
    )
