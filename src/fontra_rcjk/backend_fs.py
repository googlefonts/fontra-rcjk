import json
import logging
import os
import pathlib
import shutil
from functools import cached_property
from os import PathLike
from typing import Any

import watchfiles
from fontra.backends.designspace import cleanupWatchFilesChanges
from fontra.backends.ufo_utils import extractGlyphNameAndUnicodes
from fontra.core.classes import (
    GlobalAxis,
    GlobalDiscreteAxis,
    VariableGlyph,
    unstructure,
)
from fontra.core.instancer import mapLocationFromUserToSource
from fontra.core.protocols import WritableFontBackend
from fontTools.ufoLib.filenames import userNameToFileName

from .base import (
    GLIFGlyph,
    TimedCache,
    buildLayerGlyphsFromVariableGlyph,
    buildVariableGlyphFromLayerGlyphs,
    standardCustomDataItems,
    unpackAxes,
)

logger = logging.getLogger(__name__)

glyphSetNames = ["characterGlyph", "deepComponent", "atomicElement"]


FILE_DELETED_TOKEN = object()
DS_FILENAME = "designspace.json"
FONTLIB_FILENAME = "fontLib.json"


class RCJKBackend:
    @classmethod
    def fromPath(cls, path: PathLike) -> WritableFontBackend:
        return cls(path)

    @classmethod
    def createFromPath(cls, path: PathLike) -> WritableFontBackend:
        return cls(path, create=True)

    def __init__(self, path: PathLike, *, create: bool = False):
        self.path = pathlib.Path(path).resolve()
        if create:
            if self.path.is_dir():
                shutil.rmtree(self.path)
            elif self.path.exists():
                self.path.unlink()
            cgPath = self.path / "characterGlyph"
            cgPath.mkdir(exist_ok=True, parents=True)
            self.characterGlyphGlyphSet = RCJKGlyphSet(cgPath, self.registerWrittenPath)

        for name in glyphSetNames:
            setattr(
                self,
                name + "GlyphSet",
                RCJKGlyphSet(self.path / name, self.registerWrittenPath),
            )

        if not self.characterGlyphGlyphSet.exists():
            raise TypeError(f"Not a valid rcjk project: '{path}'")

        designspacePath = self.path / DS_FILENAME
        if designspacePath.is_file():
            self.designspace = json.loads(designspacePath.read_text(encoding="utf-8"))
        else:
            self.designspace = {}

        self._glyphMap: dict[str, list[int]] = {}
        for gs, hasEncoding in self._iterGlyphSets():
            glyphMap = gs.getGlyphMap(not hasEncoding)
            for glyphName, unicodes in glyphMap.items():
                assert glyphName not in self._glyphMap
                if not hasEncoding:
                    assert not unicodes
                self._glyphMap[glyphName] = unicodes

        self._recentlyWrittenPaths: dict[str, Any] = {}
        self._tempGlyphCache = TimedCache()

    def close(self):
        self._tempGlyphCache.cancel()

    def registerWrittenPath(self, path, *, deleted=False):
        mTime = FILE_DELETED_TOKEN if deleted else os.path.getmtime(path)
        self._recentlyWrittenPaths[os.fspath(path)] = mTime

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

    @cached_property
    def _defaultLocation(self):
        axes = unpackAxes(self.designspace.get("axes", ()))
        userLoc = {
            axis["name"]: axis["defaultValue"]
            for axis in self.designspace.get("axes", ())
        }
        return mapLocationFromUserToSource(userLoc, axes)

    async def getGlyphMap(self) -> dict[str, list[int]]:
        return dict(self._glyphMap)

    async def putGlyphMap(self, glyphMap: dict[str, list[int]]) -> None:
        pass

    async def getGlobalAxes(self) -> list[GlobalAxis | GlobalDiscreteAxis]:
        return unpackAxes(self.designspace.get("axes", ()))

    async def putGlobalAxes(self, axes: list[GlobalAxis | GlobalDiscreteAxis]) -> None:
        self.designspace["axes"] = unstructure(axes)
        if hasattr(self, "_defaultLocation"):
            del self._defaultLocation
        self._writeDesignSpaceFile()

    def _writeDesignSpaceFile(self):
        designspacePath = self.path / DS_FILENAME
        designspacePath.write_text(
            json.dumps(self.designspace, indent=2), encoding="utf-8"
        )

    async def getUnitsPerEm(self) -> int:
        return 1000

    async def putUnitsPerEm(self, value: int) -> None:
        pass

    async def getGlyph(self, glyphName: str) -> VariableGlyph | None:
        try:
            layerGlyphs = self._getLayerGlyphs(glyphName)
        except KeyError:
            return None
        return buildVariableGlyphFromLayerGlyphs(layerGlyphs)

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

        layerGlyphs = _fudgeLayerNames(glyphName, layerGlyphs)

        self._tempGlyphCache[glyphName] = layerGlyphs

        for compoName in layerGlyphs["foreground"].getComponentNames():
            self._populateGlyphCache(compoName)

    def _getLayerGLIFData(self, glyphName):
        for gs, _ in self._iterGlyphSets():
            if glyphName in gs:
                return gs.getGlyphLayerData(glyphName)
        return None

    async def putGlyph(
        self, glyphName: str, glyph: VariableGlyph, unicodes: list[int]
    ) -> None:
        if glyphName not in self._glyphMap:
            existingLayerGlyphs = {}
        else:
            existingLayerGlyphs = self._getLayerGlyphs(glyphName)
        localDefaultLocation = self._defaultLocation | {
            axis.name: axis.defaultValue for axis in glyph.axes
        }
        layerGlyphs = buildLayerGlyphsFromVariableGlyph(
            glyphName, glyph, unicodes, localDefaultLocation, existingLayerGlyphs
        )
        glyphSet = self.getGlyphSetForGlyph(glyphName)
        glyphSet.putGlyphLayerData(glyphName, layerGlyphs.items())
        self._glyphMap[glyphName] = unicodes
        self._tempGlyphCache[glyphName] = layerGlyphs

    async def deleteGlyph(self, glyphName):
        if glyphName not in self._glyphMap:
            raise KeyError(f"Glyph '{glyphName}' does not exist")

        for gs, _ in self._iterGlyphSets():
            if glyphName in gs:
                gs.deleteGlyph(glyphName)

        del self._glyphMap[glyphName]

    async def getCustomData(self) -> dict[str, Any]:
        customData = {}
        customDataPath = self.path / FONTLIB_FILENAME
        if customDataPath.is_file():
            customData = json.loads(customDataPath.read_text(encoding="utf-8"))
        return customData | standardCustomDataItems

    async def putCustomData(self, customData: dict[str, Any]) -> None:
        customDataPath = self.path / FONTLIB_FILENAME
        customData = {
            k: v
            for k, v in customData.items()
            if k not in standardCustomDataItems or standardCustomDataItems[k] != v
        }
        customDataPath.write_text(json.dumps(customData, indent=2), encoding="utf-8")

    async def watchExternalChanges(self):
        async for changes in watchfiles.awatch(self.path):
            changes = cleanupWatchFilesChanges(changes)
            glyphNames = set()
            for change, path in changes:
                mTime = (
                    FILE_DELETED_TOKEN
                    if not os.path.exists(path)
                    else os.path.getmtime(path)
                )
                if self._recentlyWrittenPaths.pop(path, None) == mTime:
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
                yield None, {"glyphs": dict.fromkeys(glyphNames)}


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
            glyphMap = {}
            for path in self.path.glob("*.glif"):
                with open(path, "rb") as f:
                    # assuming all unicodes are in the first 1024 bytes of the file
                    data = f.read(1024)
                glyphName, unicodes = extractGlyphNameAndUnicodes(data, path.name)
                if ignoreUnicodes:
                    unicodes = []
                glyphMap[glyphName] = unicodes
                self.contents[glyphName] = path
                self.glifFileNames[path.name] = glyphName
            self.glyphMap = glyphMap
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
            if layerPath is not None and layerPath.exists():
                glyphLayerData.append((layerName, layerPath.read_bytes()))
        return glyphLayerData

    def putGlyphLayerData(self, glyphName, glyphLayerData):
        mainPath = self.contents.get(glyphName)
        if mainPath is None:
            fileName = userNameToFileName(glyphName, suffix=".glif")
            mainPath = self.path / fileName
            self.contents[glyphName] = mainPath
            self.glifFileNames[mainPath.name] = glyphName

        assert mainPath.parent == self.path
        mainFileName = mainPath.name

        usedLayerNames = set()
        for layerName, layerGlyph in glyphLayerData:
            if layerName == "foreground":
                layerPath = mainPath
            else:
                # FIXME: escape / in layerName, and unescape upon read
                layerPath = self.path / layerName / mainFileName
                if layerName not in self.layers:
                    # new layer
                    self.layers[layerName] = {}
                    layerDirPath = self.path / layerName
                    layerDirPath.mkdir(exist_ok=True)
                self.layers[layerName][mainFileName] = layerPath
                usedLayerNames.add(layerName)
            existingData = layerPath.read_bytes() if layerPath.exists() else None
            newData = layerGlyph.asGLIFData().encode("utf-8")
            if newData != existingData:
                layerPath.write_bytes(newData)
                self.registerWrittenPath(layerPath)

        # Check to see if we need to delete any layer glif files
        for layerName, layerContents in self.layers.items():
            if layerName in usedLayerNames:
                continue
            layerPath = layerContents.get(mainFileName)
            if layerPath is None:
                continue
            layerPath.unlink(missing_ok=True)
            self.registerWrittenPath(layerPath, deleted=True)
            del layerContents[mainFileName]

    def deleteGlyph(self, glyphName):
        mainPath = self.contents[glyphName]
        del self.contents[glyphName]
        pathsToDelete = [mainPath]
        mainFileName = mainPath.name
        for layerName, layerContents in self.layers.items():
            layerPath = layerContents.get(mainFileName)
            if layerPath is not None:
                pathsToDelete.append(layerPath)
                del layerContents[mainFileName]
        for layerPath in pathsToDelete:
            layerPath.unlink()
            self.registerWrittenPath(layerPath, deleted=True)
        del self.glyphMap[glyphName]


def _fudgeLayerNames(glyphName, layerGlyphs):
    #
    # The rcjk format does not play well with case-insensitive file systems:
    # layer names become folder names, and to read layer names we read folder
    # names. Since layer names are global per font, case differences in layer
    # names can cause ambiguities. For example, if a layer "s2" exists, a
    # folder named "s2" will be written. If "S2" (cap S!) *also* exists, its
    # data will be happily written to the "s2" folder on a case-insensitive
    # file system. When reading back the project, we find "s2", but not "S2".
    #
    # The code below tries to detect that situation and work around it. This
    # works as long as the layer names *within a single glyph* are not
    # ambiguous: "S1" and "s1" should not co-exist in the same glyph.
    #
    # The problem can also happen when checking out an .rcjk git project on a
    # case-insensitive file system: "S2" and "s2" may both exist in the repo,
    # but on a macOS/Windows checkout only one of them will be seen.
    #
    usedLayerNames = set()
    for varData in layerGlyphs["foreground"].lib.get("robocjk.variationGlyphs", []):
        layerName = varData.get("layerName")
        if layerName:
            usedLayerNames.add(layerName)
    missingLayerNames = usedLayerNames - set(layerGlyphs)

    if not missingLayerNames:
        return layerGlyphs

    if len(usedLayerNames) != len(
        {layerName.casefold() for layerName in usedLayerNames}
    ):
        logger.warn(
            f"Possible layer name conflict on case-insensitive file system ({glyphName})"
        )
        return layerGlyphs

    renameMap = {}
    availableLayerNames = {layerName.casefold(): layerName for layerName in layerGlyphs}
    for missingLayerName in missingLayerNames:
        folded = missingLayerName.casefold()
        fudged = availableLayerNames.get(folded)
        if fudged:
            renameMap[fudged] = missingLayerName
    if renameMap:
        logger.warn(f"fudging layer names for {glyphName}: {renameMap}")
        layerGlyphs = {renameMap.get(k, k): v for k, v in layerGlyphs.items()}

    return layerGlyphs
