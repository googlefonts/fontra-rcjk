import asyncio
from datetime import datetime, timedelta
import logging
from random import random
from fontra.backends.designspace import makeGlyphMapChange
from .base import (
    GLIFGlyph,
    TimedCache,
    getComponentAxisDefaults,
    serializeGlyph,
    unserializeGlyph,
)
from .client import HTTPError


logger = logging.getLogger(__name__)


_glyphTypes = [
    # (typeCode, typeName)
    ("AE", "atomic_elements"),
    ("DC", "deep_components"),
    ("CG", "character_glyphs"),
]

_baseGlyphMethods = {
    "AE": "atomic_element_",
    "DC": "deep_component_",
    "CG": "character_glyph_",
}


class RCJKMySQLBackend:
    @classmethod
    def fromRCJKClient(cls, client, fontUID):
        self = cls()
        self.client = client
        self.fontUID = fontUID
        self.pollExternalChangesInterval = 8
        self._rcjkGlyphInfo = None
        self._glyphCache = LRUCache()
        self._tempFontItemsCache = TimedCache()
        self._lastPolledForChanges = None
        self._writingChanges = 0
        self._glyphTimeStamps = {}
        self._pollNowEvent = asyncio.Event()
        self._glyphMap = None
        return self

    def close(self):
        self._tempFontItemsCache.cancel()

    async def getGlyphMap(self):
        if self._glyphMap is None:
            self._glyphMap, self._rcjkGlyphInfo = await self._getGlyphMap()
        return dict(self._glyphMap)

    async def _getGlyphMap(self):
        rcjkGlyphInfo = {}
        glyphMap = {}
        response = await self.client.glif_list(self.fontUID)
        for typeCode, typeName in _glyphTypes:
            for glyphInfo in response["data"][typeName]:
                glyphMap[glyphInfo["name"]] = _unicodesFromGlyphInfo(glyphInfo)
                rcjkGlyphInfo[glyphInfo["name"]] = (typeCode, glyphInfo["id"])
        # TODO: self._glyphMap should be a cache once we know how to invalidate
        return glyphMap, rcjkGlyphInfo

    async def _getMiscFontItems(self):
        if not hasattr(self, "_getMiscFontItemsTask"):

            async def taskFunc():
                font_data = await self.client.font_get(self.fontUID)
                self._tempFontItemsCache["designspace"] = font_data["data"].get(
                    "designspace", {}
                )
                self._tempFontItemsCache["fontLib"] = font_data["data"].get(
                    "fontlib", {}
                )
                self._tempFontItemsCache.updateTimeOut()
                del self._getMiscFontItemsTask

            self._getMiscFontItemsTask = asyncio.create_task(taskFunc())
        await self._getMiscFontItemsTask

    async def getGlobalAxes(self):
        axes = self._tempFontItemsCache.get("axes")
        if axes is None:
            await self._getMiscFontItems()
            designspace = self._tempFontItemsCache["designspace"]
            axes = [dict(axis) for axis in designspace.get("axes", ())]
            for axis in axes:
                axis["label"] = axis["name"]
                axis["name"] = axis["tag"]
                del axis["tag"]
            self._tempFontItemsCache["axes"] = axes
        return axes

    async def getUnitsPerEm(self):
        return 1000

    async def getFontLib(self):
        fontLib = self._tempFontItemsCache.get("fontLib")
        if fontLib is None:
            await self._getMiscFontItems()
            fontLib = self._tempFontItemsCache["fontLib"]
        return fontLib

    async def getGlyph(self, glyphName):
        if self._glyphMap is not None and glyphName not in self._glyphMap:
            return None
        layerGlyphs = await self._getLayerGlyphs(glyphName)
        axisDefaults = getComponentAxisDefaults(layerGlyphs, self._glyphCache)
        return serializeGlyph(layerGlyphs, axisDefaults)

    async def _getLayerGlyphs(self, glyphName):
        layerGlyphs = self._glyphCache.get(glyphName)
        if layerGlyphs is None:
            typeCode, glyphID = self._rcjkGlyphInfo[glyphName]
            getMethodName = _getFullMethodName(typeCode, "get")
            method = getattr(self.client, getMethodName)
            response = await method(
                self.fontUID, glyphID, return_layers=True, return_related=True
            )
            self._lastPolledForChanges = response["server_datetime"]

            glyphData = response["data"]
            self._glyphTimeStamps[glyphName] = getUpdatedTimeStamp(glyphData)
            self._populateGlyphCache(glyphName, glyphData)
            layerGlyphs = self._glyphCache[glyphName]
        return layerGlyphs

    def _populateGlyphCache(self, glyphName, glyphData):
        if glyphName in self._glyphCache:
            return
        self._glyphCache[glyphName] = buildLayerGlyphs(glyphData)
        for subGlyphData in glyphData.get("made_of", ()):
            subGlyphName = subGlyphData["name"]
            typeCode, glyphID = self._rcjkGlyphInfo[subGlyphName]
            assert typeCode == subGlyphData["type_code"]
            assert glyphID == subGlyphData["id"]
            self._populateGlyphCache(subGlyphName, subGlyphData)

    async def putGlyph(self, glyphName, glyph):
        logger.info(f"Start writing {glyphName}")
        self._writingChanges += 1
        try:
            return await self._putGlyph(glyphName, glyph)
        finally:
            self._writingChanges -= 1
            logger.info(f"Done writing {glyphName}")

    async def _putGlyph(self, glyphName, glyph):
        layerGlyphs = unserializeGlyph(
            glyphName, glyph, self._glyphMap.get(glyphName, [])
        )
        typeCode, glyphID = self._rcjkGlyphInfo.get(glyphName, ("CG", None))
        if glyphID is None:
            raise NotImplementedError("creating new glyphs is yet to be implemented")

        try:
            lockResponse = await self._callGlyphMethod(
                glyphName, "lock", return_data=False
            )
        except HTTPError as error:
            return f"Can't lock glyph ({error})"

        errorMessage = None

        try:
            glyphTimeStamp = self._glyphTimeStamps[glyphName]
            currentTimeStamp = getUpdatedTimeStamp(lockResponse["data"])
            if glyphTimeStamp != currentTimeStamp:
                errorMessage = "Someone else made an edit just before you."
            else:
                existingLayerData = {
                    k: v.cachedGLIFData
                    for k, v in self._glyphCache.get(glyphName, {}).items()
                }
                for layerName, layerGlyph in layerGlyphs.items():
                    xmlData = layerGlyph.asGLIFData()
                    if xmlData == existingLayerData.get(layerName):
                        # There was no change in the xml data, skip the update
                        continue
                    if layerName == "foreground":
                        args = (glyphName, "update", xmlData)
                    else:
                        args = (glyphName, "layer_update", layerName, xmlData)
                    await self._callGlyphMethod(
                        *args,
                        return_data=False,
                        return_layers=False,
                    )
                self._glyphCache[glyphName] = layerGlyphs
        finally:
            unlockResponse = await self._callGlyphMethod(
                glyphName, "unlock", return_data=False
            )
            if errorMessage:
                asyncio.get_running_loop().call_soon(self._pollNowEvent.set)

        if errorMessage is None:
            self._glyphTimeStamps[glyphName] = getUpdatedTimeStamp(
                unlockResponse["data"]
            )

        return errorMessage

    async def _callGlyphMethod(self, glyphName, methodName, *args, **kwargs):
        typeCode, glyphID = self._rcjkGlyphInfo.get(glyphName, ("CG", None))
        assert glyphID is not None
        apiMethodName = _getFullMethodName(typeCode, methodName)
        method = getattr(self.client, apiMethodName)
        return await method(self.fontUID, glyphID, *args, **kwargs)

    async def watchExternalChanges(self):
        errorDelay = 30
        while True:
            try:
                externalChange, reloadPattern = await self._pollOnceForChanges()
            except Exception as e:
                logger.error("error while polling for changes: %r", e)
                logger.info(f"pausing the poll loop for {errorDelay} seconds")
                await asyncio.sleep(errorDelay)
            else:
                if externalChange or reloadPattern:
                    yield externalChange, reloadPattern

    async def _pollOnceForChanges(self):
        await asyncio.wait(
            [
                asyncio.sleep(self.pollExternalChangesInterval + 2 * random()),
                self._pollNowEvent.wait(),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )
        self._pollNowEvent.clear()
        if self._lastPolledForChanges is None:
            # No glyphs have been requested, so there's nothing to update
            return
        if self._writingChanges:
            # We're in the middle of writing changes, let's skip a round
            return
        response = await self.client.glif_list(
            self.fontUID,
            updated_since=fudgeTimeStamp(self._lastPolledForChanges),
        )
        responseData = response["data"]
        glyphNames = set()
        glyphMapUpdates = {}
        latestTimeStamp = ""  # less than any timestamp string
        for typeCode, typeName in _glyphTypes:
            for glyphInfo in responseData[typeName]:
                glyphName = glyphInfo["name"]
                glyphUpdatedAt = getUpdatedTimeStamp(glyphInfo)
                latestTimeStamp = max(latestTimeStamp, glyphUpdatedAt)

                if glyphUpdatedAt == self._glyphTimeStamps.get(glyphName):
                    # We made this change, or otherwise we already saw it
                    continue

                if glyphName not in self._rcjkGlyphInfo:
                    assert glyphName not in self._glyphMap
                    logger.info(f"New glyph {glyphName}")
                    self._rcjkGlyphInfo[glyphName] = (typeCode, glyphInfo["id"])
                else:
                    assert glyphName in self._glyphMap

                unicodes = _unicodesFromGlyphInfo(glyphInfo)
                if unicodes != self._glyphMap.get(glyphName):
                    self._glyphMap[glyphName] = unicodes
                    glyphMapUpdates[glyphName] = unicodes

                glyphNames.add(glyphName)
                self._glyphCache.pop(glyphName, None)

        if not latestTimeStamp:
            latestTimeStamp = response["server_datetime"]

        self._lastPolledForChanges = latestTimeStamp

        reloadPattern = {"glyphs": dict.fromkeys(glyphNames)} if glyphNames else None
        externalChange = makeGlyphMapChange(glyphMapUpdates)
        return externalChange, reloadPattern


def _unicodesFromGlyphInfo(glyphInfo):
    unicode_hex = glyphInfo.get("unicode_hex")
    return [int(unicode_hex, 16)] if unicode_hex else []


def getUpdatedTimeStamp(info):
    timeStamp = info["updated_at"]
    layers_updated_at = info.get("layers_updated_at")
    if layers_updated_at:
        timeStamp = max(timeStamp, layers_updated_at)
    return timeStamp


def buildLayerGlyphs(glyphData):
    layerGLIFData = [("foreground", glyphData["data"])]
    layerGLIFData.extend(
        (layer["group_name"], layer["data"]) for layer in glyphData.get("layers", ())
    )
    layerGlyphs = {}
    for layerName, glifData in layerGLIFData:
        layerGlyphs[layerName] = GLIFGlyph.fromGLIFData(glifData)
    return layerGlyphs


def _getFullMethodName(typeCode, methodName):
    return _baseGlyphMethods[typeCode] + methodName


class LRUCache(dict):
    """A quick and dirty Least Recently Used cache, which leverages the fact
    that dictionaries keep their insertion order.
    """

    def __init__(self, maxSize=128):
        assert isinstance(maxSize, int)
        assert maxSize > 0
        self._maxSize = maxSize

    def get(self, key, default=None):
        # Override so we get our custom __getitem__ behavior
        try:
            value = self[key]
        except KeyError:
            value = default
        return value

    def __getitem__(self, key):
        value = super().__getitem__(key)
        # Move key/value to the end
        del self[key]
        self[key] = value
        return value

    def __setitem__(self, key, value):
        if key in self:
            # Ensure key/value get inserted at the end
            del self[key]
        super().__setitem__(key, value)
        while len(self) > self._maxSize:
            del self[next(iter(self))]


def fudgeTimeStamp(isoString):
    """Add one millisecond to the timestamp, so we can account for differences
    in the microsecond range.
    """
    one_millisecond = timedelta(milliseconds=1)
    d = datetime.fromisoformat(isoString)
    d = d + one_millisecond
    return d.isoformat()
