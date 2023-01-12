import json
import os
import pathlib
import watchfiles
from fontra.backends.ufo_utils import extractGlyphNameAndUnicodes
from .base import (
    GLIFGlyph,
    TimedCache,
    getComponentAxisDefaults,
    serializeGlyph,
    unserializeGlyph,
)


glyphSetNames = ["characterGlyph", "deepComponent", "atomicElement"]


class RCJKBackend:
    @classmethod
    def fromPath(cls, path):
        return cls(path)

    def __init__(self, path):
        self.path = pathlib.Path(path).resolve()
        for name in glyphSetNames:
            setattr(
                self,
                name + "GlyphSet",
                RCJKGlyphSet(self.path / name, self.registerWrittenPath),
            )

        if not self.characterGlyphGlyphSet.exists():
            raise TypeError(f"Not a valid rcjk project: '{path}'")

        designspacePath = self.path / "designspace.json"
        if designspacePath.is_file():
            self.designspace = json.loads(designspacePath.read_bytes())
        else:
            self.designspace = {}

        self._glyphMap = {}
        for gs, hasEncoding in self._iterGlyphSets():
            glyphMap = gs.getGlyphMap(not hasEncoding)
            for glyphName, unicodes in glyphMap.items():
                assert glyphName not in self._glyphMap
                if not hasEncoding:
                    assert not unicodes
                self._glyphMap[glyphName] = unicodes

        self._recentlyWrittenPaths = {}
        self._tempGlyphCache = TimedCache()

    def close(self):
        self._tempGlyphCache.cancel()

    def registerWrittenPath(self, path):
        self._recentlyWrittenPaths[os.fspath(path)] = os.path.getmtime(path)

    def _iterGlyphSets(self):
        yield self.characterGlyphGlyphSet, True
        yield self.deepComponentGlyphSet, False
        yield self.atomicElementGlyphSet, False

    def getGlyphSetForGlyph(self, glyphName):
        if glyphName in self.atomicElementGlyphSet:
            return self.atomicElementGlyphSet
        elif glyphName in self.deepComponentGlyphSet:
            return self.deepComponentGlyphSet
        else:
            # Default for new glyphs, too
            return self.characterGlyphGlyphSet

    async def getGlyphMap(self):
        return self._glyphMap

    async def getGlobalAxes(self):
        axes = getattr(self, "_globalAxes", None)
        if axes is None:
            axes = []
            for axis in self.designspace.get("axes", ()):
                axis = dict(axis)
                axis["label"] = axis["name"]
                axis["name"] = axis["tag"]
                del axis["tag"]
                axes.append(axis)
            self._globalAxes = axes
        return axes

    async def getUnitsPerEm(self):
        return 1000

    async def getGlyph(self, glyphName):
        layerGlyphs = self._getLayerGlyphs(glyphName)
        axisDefaults = getComponentAxisDefaults(layerGlyphs, self._tempGlyphCache)
        return serializeGlyph(layerGlyphs, axisDefaults)

    def _getLayerGlyphs(self, glyphName):
        layerGlyphs = self._tempGlyphCache.get(glyphName)
        if layerGlyphs is None:
            self._populateGlyphCache(glyphName)
            self._tempGlyphCache.updateTimeOut()
            layerGlyphs = self._tempGlyphCache[glyphName]
        return layerGlyphs

    def _populateGlyphCache(self, glyphName):
        if glyphName in self._tempGlyphCache:
            return
        layerGLIFData = self._getLayerGLIFData(glyphName)
        if layerGLIFData is None:
            return

        layerGlyphs = {}
        for layerName, glifData in layerGLIFData:
            layerGlyphs[layerName] = GLIFGlyph.fromGLIFData(glifData)
        self._tempGlyphCache[glyphName] = layerGlyphs

        for compoName in layerGlyphs["foreground"].getComponentNames():
            self._populateGlyphCache(compoName)

    def _getLayerGLIFData(self, glyphName):
        for gs, _ in self._iterGlyphSets():
            if glyphName in gs:
                return gs.getGlyphLayerData(glyphName)
        return None

    async def putGlyph(self, glyphName, glyph):
        layerGlyphs = unserializeGlyph(
            glyphName, glyph, self._glyphMap.get(glyphName, [])
        )
        glyphSet = self.getGlyphSetForGlyph(glyphName)
        glyphSet.putGlyphLayerData(glyphName, layerGlyphs.items())

    async def getFontLib(self):
        libPath = self.path / "fontLib.json"
        if libPath.is_file():
            return json.loads(libPath.read_text(encoding="utf-8"))
        return {}

    async def watchExternalChanges(self):
        async for changes in watchfiles.awatch(self.path):
            glyphNames = set()
            for change, path in changes:
                if self._recentlyWrittenPaths.pop(path, None) == os.path.getmtime(path):
                    # We made this change ourselves, so it is not an external change
                    continue
                fileName = os.path.basename(path)
                for gs, _ in self._iterGlyphSets():
                    glyphName = gs.glifFileNames.get(fileName)
                    if glyphName is not None:
                        break
                if glyphName is not None:
                    glyphNames.add(glyphName)
            if glyphNames:
                self._tempGlyphCache.clear()
                yield glyphNames


class RCJKGlyphSet:
    def __init__(self, path, registerWrittenPath):
        self.path = path
        self.registerWrittenPath = registerWrittenPath
        self.glyphMap = None
        self.contents = {}  # glyphName: path
        self.glifFileNames = {}  # fileName: glyphName
        self.layers = {}
        self.setupLayers()

    def exists(self):
        return self.path.is_dir()

    def setupLayers(self):
        if not self.exists():
            return
        for layerDir in sorted(self.path.iterdir()):
            if layerDir.is_dir():
                glifPaths = {
                    glifPath.name: glifPath for glifPath in layerDir.glob("*.glif")
                }
                if glifPaths:
                    self.layers[layerDir.name] = glifPaths

    def getGlyphMap(self, ignoreUnicodes=False):
        if self.glyphMap is None:
            glyphNames = {}
            for path in self.path.glob("*.glif"):
                with open(path, "rb") as f:
                    # assuming all unicodes are in the first 1024 bytes of the file
                    data = f.read(1024)
                glyphName, unicodes = extractGlyphNameAndUnicodes(data, path.name)
                if ignoreUnicodes:
                    unicodes = []
                glyphNames[glyphName] = unicodes
                self.contents[glyphName] = path
                self.glifFileNames[path.name] = glyphName
            self.glyphMap = glyphNames
        return self.glyphMap

    def __contains__(self, glyphName):
        return glyphName in self.contents

    def getGlyphLayerData(self, glyphName):
        mainPath = self.contents.get(glyphName)
        if mainPath is None:
            return None
        mainFileName = mainPath.name
        glyphLayerData = [("foreground", mainPath.read_bytes())]
        for layerName, layerContents in self.layers.items():
            layerPath = layerContents.get(mainFileName)
            if layerPath is not None:
                glyphLayerData.append((layerName, layerPath.read_bytes()))
        return glyphLayerData

    def putGlyphLayerData(self, glyphName, glyphLayerData):
        mainPath = self.contents.get(glyphName)
        if mainPath is None:
            # fileName = userNameToFileName(glyphName, ..., ".glif")
            # mainPath = self.path / fileName
            # self.contents[glyphName] = mainPath
            raise NotImplementedError("creating new glyphs is yet to be implemented")
        assert mainPath.parent == self.path
        mainFileName = mainPath.name

        for layerName, layerGlyph in glyphLayerData:
            if layerName == "foreground":
                layerPath = mainPath
            else:
                # FIXME: escape / in layerName, and unescape upon read
                layerPath = self.path / layerName / mainFileName
                self.layers[layerName][mainFileName] = layerPath
            existingData = layerPath.read_bytes() if layerPath.exists() else None
            newData = layerGlyph.asGLIFData().encode("utf-8")
            if newData != existingData:
                layerPath.write_bytes(newData)
                self.registerWrittenPath(layerPath)
