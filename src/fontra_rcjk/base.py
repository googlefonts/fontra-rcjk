import asyncio
from copy import deepcopy
from dataclasses import asdict
from functools import cached_property

from fontra.backends.designspace import cleanAffine, makeAffineTransform
from fontra.core.classes import (
    Component,
    Layer,
    LocalAxis,
    Source,
    StaticGlyph,
    Transformation,
    VariableGlyph,
)
from fontra.core.packedpath import PackedPathPointPen
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
        readGlyphFromString(glifData, self, pen)
        self.path = pen.getPath()
        self.components = pen.components
        return self

    @classmethod
    def fromStaticGlyph(cls, glyphName, staticGlyph):
        self = cls()
        self.name = glyphName
        self.width = staticGlyph.xAdvance
        self.path = staticGlyph.path
        for component in staticGlyph.components:
            if component.location:
                self.variableComponents.append(component)
            else:
                # classic component
                self.components.append(component)
        return self

    def asGLIFData(self):
        return writeGlyphToString(self.name, self, self.drawPoints, validate=False)

    @cached_property
    def cachedGLIFData(self):
        return self.asGLIFData()

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
                cleanAffine(makeAffineTransform(component.transformation)),
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

    def serialize(self):
        return StaticGlyph(
            xAdvance=self.width,
            path=deepcopy(self.path),
            components=deepcopy(self.components),
        )


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


def getComponentAxisDefaults(layerGlyphs, layerGlyphCache):
    axisDefaults = {}
    for componentGlyphName in layerGlyphs["foreground"].getComponentNames():
        componentGlyph = layerGlyphCache.get(componentGlyphName)
        if componentGlyph is not None:
            axisDefaults[componentGlyphName] = {
                axis.name: axis.defaultValue
                for axis in componentGlyph["foreground"].axes
            }
    return axisDefaults


def serializeGlyph(layerGlyphs, axisDefaults):
    layers = {
        layerName: Layer(glyph=glyph.serialize())
        for layerName, glyph in layerGlyphs.items()
    }

    defaultGlyph = layerGlyphs["foreground"]
    defaultComponents = serializeComponents(
        defaultGlyph.lib.get("robocjk.deepComponents", ()), axisDefaults, None, None
    )
    if defaultComponents:
        layers["foreground"].glyph.components = defaultComponents

    dcNames = [c.name for c in defaultComponents]
    defaultComponentLocations = [compo.location for compo in defaultComponents]

    sources = [
        Source(
            name="<default>",
            layerName="foreground",
            customData={FONTRA_STATUS_KEY: defaultGlyph.lib.get("robocjk.status", 0)},
        )
    ]
    variationGlyphData = defaultGlyph.lib.get("robocjk.variationGlyphs", ())
    for sourceIndex, varDict in enumerate(variationGlyphData, 1):
        inactiveFlag = not varDict.get("on", True)
        layerName = varDict.get("layerName")
        sourceName = varDict.get("sourceName")
        if not sourceName:
            sourceName = layerName if layerName else f"source_{sourceIndex}"
        if not layerName:
            layerName = f"{sourceName}_{sourceIndex}_layer"
            assert layerName not in layers, layerName

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

        components = serializeComponents(
            varDict.get("deepComponents", ()),
            axisDefaults,
            dcNames,
            defaultComponentLocations,
        )
        if components:
            layerGlyph.components = components

        location = varDict["location"]
        sources.append(
            Source(
                name=sourceName,
                location=location,
                layerName=layerName,
                inactive=inactiveFlag,
                customData={FONTRA_STATUS_KEY: varDict.get("status", 0)},
            )
        )

    return VariableGlyph(
        name=defaultGlyph.name,
        axes=defaultGlyph.axes,
        sources=sources,
        layers=layers,
    )


def serializeComponents(
    deepComponents, axisDefaults, dcNames, neutralComponentLocations
):
    if neutralComponentLocations is None:
        neutralComponentLocations = [{}] * len(deepComponents)
    components = []
    for index, deepCompoDict in enumerate(deepComponents):
        name = deepCompoDict["name"] if "name" in deepCompoDict else dcNames[index]
        component = Component(name)
        if deepCompoDict["coord"]:
            component.location = cleanupLocation(
                deepCompoDict["coord"],
                axisDefaults.get(name),
                neutralComponentLocations[index],
            )
        component.transformation = convertTransformation(deepCompoDict["transform"])
        components.append(component)
    return components


def cleanupLocation(location, axisDefaults, neutralLocation):
    if axisDefaults is None:
        return dict(location)
    return {
        a: location.get(a, neutralLocation.get(a, v)) for a, v in axisDefaults.items()
    }


def convertTransformation(rcjkTransformation):
    t = rcjkTransformation
    return Transformation(
        translateX=t["x"],
        translateY=t["y"],
        rotation=t["rotation"],
        scaleX=t["scalex"],
        scaleY=t["scaley"],
        tCenterX=t["tcenterx"],
        tCenterY=t["tcentery"],
    )


def unserializeGlyph(glyphName, glyph, unicodes, defaultLocation):
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
        layerGlyphs[layerName] = GLIFGlyph.fromStaticGlyph(glyphName, layer.glyph)
        layerGlyphs[layerName].unicodes = unicodes
    defaultGlyph = layerGlyphs["foreground"]

    if glyph.axes:
        defaultGlyph.lib["robocjk.axes"] = [asdict(axis) for axis in glyph.axes]

    deepComponents = unserializeComponents(defaultGlyph.variableComponents)
    if deepComponents:
        defaultGlyph.lib["robocjk.deepComponents"] = deepComponents

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

        deepComponents = unserializeComponents(layerGlyph.variableComponents)
        if deepComponents:
            varDict["deepComponents"] = deepComponents

        if layerGlyph.hasOutlineOrClassicComponents():
            varDict["layerName"] = source.layerName
        else:
            varDict["layerName"] = ""  # Mimic RoboCJK
            # This is a "virtual" layer: all info will go to defaultGlyph.lib,
            # and no "true" layer will be written
            del layerGlyphs[source.layerName]

        variationGlyphs.append(varDict)

    if variationGlyphs:
        defaultGlyph.lib["robocjk.variationGlyphs"] = variationGlyphs

    return layerGlyphs


def unserializeComponents(variableComponents):
    components = []
    for compo in variableComponents:
        compoDict = dict(name=compo.name)
        compoDict.update(
            coord=compo.location,
            transform=unconvertTransformation(compo.transformation),
        )
        components.append(compoDict)
    return components


def unconvertTransformation(transformation):
    if transformation.skewX or transformation.skewY:
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
