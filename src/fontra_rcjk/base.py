import asyncio
from copy import deepcopy
from dataclasses import asdict
from functools import cached_property
from fontTools.ufoLib.glifLib import readGlyphFromString, writeGlyphToString
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
from fontra.backends.designspace import cleanAffine, makeAffineTransform


class GLIFGlyph:
    def __init__(self):
        self.unicodes = []
        self.width = 0
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
        return writeGlyphToString(self.name, self, self.drawPoints)

    @cached_property
    def cachedGLIFData(self):
        return self.asGLIFData()

    def hasOutlineOrClassicComponents(self):
        return True if self.path.coordinates or self.components else False

    def drawPoints(self, pen):
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
            xAdvance=self.width, path=deepcopy(self.path), components=deepcopy(self.components)
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
        if components:
            layerGlyph.components = components

        assert componentNames == [c.name for c in layerGlyph.components]
        location = varDict["location"]
        sources.append(Source(name=sourceName, location=location, layerName=layerName))

    return VariableGlyph(
        name=defaultGlyph.name,
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


def unserializeGlyph(glyphName, glyph, unicodes):
    layerGlyphs = {}
    for layer in glyph.layers:
        assert layer.name not in layerGlyphs
        layerGlyphs[layer.name] = GLIFGlyph.fromStaticGlyph(glyphName, layer.glyph)
        layerGlyphs[layer.name].unicodes = unicodes
    defaultGlyph = layerGlyphs["foreground"]

    if glyph.axes:
        defaultGlyph.lib["robocjk.axes"] = [asdict(axis) for axis in glyph.axes]

    deepComponents = unserializeComponents(defaultGlyph.variableComponents, True)
    if deepComponents:
        defaultGlyph.lib["robocjk.deepComponents"] = deepComponents

    variationGlyphs = []
    for source in glyph.sources:
        if source.layerName == "foreground":
            # This is the default glyph, we don't treat it like a layer in .rcjk
            continue

        layerGlyph = layerGlyphs[source.layerName]
        varDict = {"sourceName": source.name, "on": True, "location": source.location}
        if layerGlyph.width != defaultGlyph.width:
            varDict["width"] = layerGlyph.width

        deepComponents = unserializeComponents(layerGlyph.variableComponents, False)
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


def unserializeComponents(variableComponents, addNames):
    components = []
    for compo in variableComponents:
        if addNames:
            compoDict = dict(name=compo.name)
        else:
            compoDict = {}
        compoDict.update(
            coord=compo.location,
            transform=unconvertTransformation(compo.transformation),
        )
        components.append(compoDict)
    return components


def unconvertTransformation(transformation):
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
