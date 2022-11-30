import asyncio
from .base import (
    GLIFGlyph,
    TimedCache,
    getComponentAxisDefaults,
    serializeGlyph,
    unserializeGlyph,
)
from .client import HTTPError


class RCJKMySQLBackend:
    @classmethod
    def fromRCJKClient(cls, client, fontUID):
        self = cls()
        self.client = client
        self.fontUID = fontUID
        self._glyphMapping = None
        self._tempGlyphCache = TimedCache()
        self._tempFontItemsCache = TimedCache()
        self._lastPolledForChanges = None
        self._writingChanges = 0
        self._writtenGlyphTimeStamps = {}
        return self

    def close(self):
        self._tempGlyphCache.cancel()
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
        axisDefaults = getComponentAxisDefaults(layerGlyphs, self._tempGlyphCache)
        return serializeGlyph(layerGlyphs, axisDefaults)

    async def _getLayerGlyphs(self, glyphName):
        layerGlyphs = self._tempGlyphCache.get(glyphName)
        if layerGlyphs is None:
            typeCode, glyphID = self._glyphMapping[glyphName]
            getMethodName = _getFullMethodName(typeCode, "get")
            method = getattr(self.client, getMethodName)
            response = await method(
                self.fontUID, glyphID, return_layers=True, return_related=True
            )
            self._lastPolledForChanges = response["server_datetime"]

            glyphData = response["data"]
            self._populateGlyphCache(glyphName, glyphData)
            self._tempGlyphCache.updateTimeOut()
            layerGlyphs = self._tempGlyphCache[glyphName]
        return layerGlyphs

    def _populateGlyphCache(self, glyphName, glyphData):
        if glyphName in self._tempGlyphCache:
            return
        self._tempGlyphCache[glyphName] = buildLayerGlyphs(glyphData)
        for subGlyphData in glyphData.get("made_of", ()):
            subGlyphName = subGlyphData["name"]
            typeCode, glyphID = self._glyphMapping[subGlyphName]
            assert typeCode == subGlyphData["type_code"]
            assert glyphID == subGlyphData["id"]
            self._populateGlyphCache(subGlyphName, subGlyphData)

    async def putGlyph(self, glyphName, glyph):
        self._writingChanges += 1
        try:
            return await self._putGlyph(glyphName, glyph)
        finally:
            self._writingChanges -= 1

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
            print("can't lock glyph", error)
            raise

        try:
            for layerName, layerGlyph in layerGlyphs.items():
                xmlData = layerGlyph.asGLIFData()
                if layerName == "foreground":
                    args = (glyphName, "update", xmlData)
                else:
                    args = (glyphName, "layer_update", layerName, xmlData)
                updateResponse = await self._callGlyphMethod(
                    *args,
                    return_data=False,
                    return_layers=False,
                )
        finally:
            unlockResponse = await self._callGlyphMethod(
                glyphName, "unlock", return_data=False
            )

        self._writtenGlyphTimeStamps[glyphName] = getUpdatedTimeStamp(
            unlockResponse["data"]
        )

    async def _callGlyphMethod(self, glyphName, methodName, *args, **kwargs):
        typeCode, glyphID = self._glyphMapping.get(glyphName, ("CG", None))
        assert glyphID is not None
        apiMethodName = _getFullMethodName(typeCode, methodName)
        method = getattr(self.client, apiMethodName)
        return await method(self.fontUID, glyphID, *args, **kwargs)

    def watchExternalChanges(self):
        async def glifWatcher():
            while True:
                await asyncio.sleep(5)
                if self._lastPolledForChanges is None:
                    # No glyphs have been requested, so there's nothing to update
                    continue
                if self._writingChanges:
                    # We're in the middle of writing changes, let's skip a round
                    continue
                response = await self.client.glif_list(
                    self.fontUID, updated_since=self._lastPolledForChanges
                )
                responseData = response["data"]
                glyphNames = set()
                latestTimeStamp = ""  # less than any timestamp string
                for k in ["atomic_elements", "character_glyphs", "deep_components"]:
                    for glyphInfo in responseData[k]:
                        glyphName = glyphInfo["name"]
                        glyphUpdatedAt = getUpdatedTimeStamp(glyphInfo)
                        latestTimeStamp = max(latestTimeStamp, glyphUpdatedAt)
                        if glyphUpdatedAt == self._writtenGlyphTimeStamps.pop(
                            glyphName, None
                        ):
                            continue
                        glyphNames.add(glyphName)
                        self._tempGlyphCache.pop(glyphName, None)

                if glyphNames:
                    print(glyphNames)
                    yield glyphNames

                if not latestTimeStamp:
                    latestTimeStamp = response["server_datetime"]

                self._lastPolledForChanges = latestTimeStamp

        return glifWatcher()


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
