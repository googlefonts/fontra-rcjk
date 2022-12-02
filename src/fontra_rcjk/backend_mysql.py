import asyncio
from datetime import datetime, timedelta
import logging
from random import random
from .base import (
    GLIFGlyph,
    TimedCache,
    getComponentAxisDefaults,
    serializeGlyph,
    unserializeGlyph,
)
from .client import HTTPError


logger = logging.getLogger(__name__)


class RCJKMySQLBackend:
    @classmethod
    def fromRCJKClient(cls, client, fontUID):
        self = cls()
        self.client = client
        self.fontUID = fontUID
        self.watchExternalChangesInterval = 5
        self._glyphMapping = None
        self._glyphCache = LRUCache()
        self._tempFontItemsCache = TimedCache()
        self._lastPolledForChanges = None
        self._writingChanges = 0
        self._glyphTimeStamps = {}
        return self

    def close(self):
        self._glyphCache.cancel()
        self._tempFontItemsCache.cancel()

    async def getReverseCmap(self):
        self._glyphMapping = {}
        revCmap = {}
        response = await self.client.glif_list(self.fontUID)
        glyphTypes = [
            ("AE", "atomic_elements"),
            ("DC", "deep_components"),
            ("CG", "character_glyphs"),
        ]
        for typeCode, typeName in glyphTypes:
            for glyphInfo in response["data"][typeName]:
                unicode_hex = glyphInfo.get("unicode_hex")
                if unicode_hex:
                    unicodes = [int(unicode_hex, 16)]
                else:
                    unicodes = []
                revCmap[glyphInfo["name"]] = unicodes
                self._glyphMapping[glyphInfo["name"]] = (typeCode, glyphInfo["id"])
        return revCmap

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
        layerGlyphs = await self._getLayerGlyphs(glyphName)
        axisDefaults = getComponentAxisDefaults(layerGlyphs, self._glyphCache)
        return serializeGlyph(layerGlyphs, axisDefaults)

    async def _getLayerGlyphs(self, glyphName):
        layerGlyphs = self._glyphCache.get(glyphName)
        if layerGlyphs is None:
            typeCode, glyphID = self._glyphMapping[glyphName]
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
            typeCode, glyphID = self._glyphMapping[subGlyphName]
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
        layerGlyphs = unserializeGlyph(glyphName, glyph)
        typeCode, glyphID = self._glyphMapping.get(glyphName, ("CG", None))
        if glyphID is None:
            raise NotImplementedError("creating new glyphs is yet to be implemented")

        try:
            lockResponse = await self._callGlyphMethod(
                glyphName, "lock", return_data=False
            )
        except HTTPError as error:
            return f"Can't lock glyph ({error})"

        try:
            glyphTimeStamp = self._glyphTimeStamps[glyphName]
            currentTimeStamp = getUpdatedTimeStamp(lockResponse["data"])
            if glyphTimeStamp != currentTimeStamp:
                return "Someone else made an edit just before you."

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
                updateResponse = await self._callGlyphMethod(
                    *args,
                    return_data=False,
                    return_layers=False,
                )
            self._glyphCache[glyphName] = layerGlyphs
        finally:
            unlockResponse = await self._callGlyphMethod(
                glyphName, "unlock", return_data=False
            )

        self._glyphTimeStamps[glyphName] = getUpdatedTimeStamp(unlockResponse["data"])

    async def _callGlyphMethod(self, glyphName, methodName, *args, **kwargs):
        typeCode, glyphID = self._glyphMapping.get(glyphName, ("CG", None))
        assert glyphID is not None
        apiMethodName = _getFullMethodName(typeCode, methodName)
        method = getattr(self.client, apiMethodName)
        return await method(self.fontUID, glyphID, *args, **kwargs)

    def watchExternalChanges(self):
        async def databaseWatcher():
            while True:
                await asyncio.sleep(self.watchExternalChangesInterval + 2 * random())
                if self._lastPolledForChanges is None:
                    # No glyphs have been requested, so there's nothing to update
                    continue
                if self._writingChanges:
                    # We're in the middle of writing changes, let's skip a round
                    continue
                response = await self.client.glif_list(
                    self.fontUID,
                    updated_since=fudgeTimeStamp(self._lastPolledForChanges),
                )
                responseData = response["data"]
                glyphNames = set()
                latestTimeStamp = ""  # less than any timestamp string
                for k in ["atomic_elements", "character_glyphs", "deep_components"]:
                    for glyphInfo in responseData[k]:
                        glyphName = glyphInfo["name"]
                        glyphUpdatedAt = getUpdatedTimeStamp(glyphInfo)
                        latestTimeStamp = max(latestTimeStamp, glyphUpdatedAt)
                        if glyphUpdatedAt == self._glyphTimeStamps.get(glyphName):
                            continue
                        glyphNames.add(glyphName)
                        self._glyphCache.pop(glyphName, None)

                if glyphNames:
                    yield glyphNames

                if not latestTimeStamp:
                    latestTimeStamp = response["server_datetime"]

                self._lastPolledForChanges = latestTimeStamp

        return databaseWatcher()


def getUpdatedTimeStamp(info):
    timeStamp = info["updated_at"]
    if info["layers_updated_at"]:
        timeStamp = max(timeStamp, info["layers_updated_at"])
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


_baseGlyphMethods = {
    "AE": "atomic_element_",
    "DC": "deep_component_",
    "CG": "character_glyph_",
}


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
        # Override to we get our custom __getitem__ behavior
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
