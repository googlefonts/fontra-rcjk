import asyncio
from functools import cached_property
from fontTools.ufoLib.glifLib import readGlyphFromString
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


class GLIFGlyph:
    @classmethod
    def fromGLIFData(cls, glifData):
        self = cls()
        self.unicodes = []
        self.width = 0
        pen = PackedPathPointPen()
        readGlyphFromString(glifData, self, pen)
        self.path = pen.getPath()
        self.components = pen.components
        return self

    @cached_property
    def axes(self):
        return [cleanupAxis(axis) for axis in self.lib.get("robocjk.axes", ())]

    def getComponentNames(self):
        classicComponentNames = {compo["name"] for compo in self.components}
        deepComponentNames = {
            compo["name"] for compo in self.lib.get("robocjk.deepComponents", ())
        }
        return sorted(classicComponentNames | deepComponentNames)

    def serialize(self):
        return StaticGlyph(
            xAdvance=self.width, path=self.path, components=self.components
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
        layerName: Layer(name=layerName, glyph=glyph.serialize())
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
    componentNames = [c.name for c in layers["foreground"].glyph.components]

    sources = [Source(name="<default>", layerName="foreground")]
    variationGlyphData = defaultGlyph.lib.get("robocjk.variationGlyphs", ())
    for sourceIndex, varDict in enumerate(variationGlyphData, 1):
        if not varDict.get("on", True):
            # XXX TODO add support for "on flag"
            continue
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
            layers[layerName] = Layer(name=layerName, glyph=layerGlyph)

        if "width" in varDict:
            xAdvance = varDict["width"]
        layerGlyph.xAdvance = xAdvance

        components = serializeComponents(
            varDict.get("deepComponents", ()),
            axisDefaults,
            dcNames,
            defaultComponentLocations,
        )
        layerGlyph.components = components

        assert componentNames == [c.name for c in layerGlyph.components]
        location = varDict["location"]
        sources.append(Source(name=sourceName, location=location, layerName=layerName))

    return VariableGlyph(
        name=defaultGlyph.name,
        unicodes=defaultGlyph.unicodes,
        axes=defaultGlyph.axes,
        sources=sources,
        layers=list(layers.values()),
    )


def serializeComponents(
    deepComponents, axisDefaults, dcNames, neutralComponentLocations
):
    if dcNames is not None:
        assert len(deepComponents) == len(dcNames)
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
