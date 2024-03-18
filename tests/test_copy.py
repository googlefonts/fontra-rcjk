import pathlib
from contextlib import aclosing

from fontra.backends import getFileSystemBackend, newFileSystemBackend
from fontra.backends.copy import copyFont

dataDir = pathlib.Path(__file__).resolve().parent / "data"
testFontPath = dataDir / "figArnaud.rcjk"


async def test_copy_font(tmpdir):
    tmpdir = pathlib.Path(tmpdir)
    destPath = tmpdir / "test.rcjk"
    srcFont = getFileSystemBackend(testFontPath)
    destFont = newFileSystemBackend(destPath)
    async with aclosing(srcFont), aclosing(destFont):
        await copyFont(srcFont, destFont)
        dupedFont = getFileSystemBackend(testFontPath)
        async with aclosing(dupedFont):
            glyphMap = await srcFont.getGlyphMap()
            assert glyphMap == await dupedFont.getGlyphMap()
            assert await srcFont.getFontInfo() == await dupedFont.getFontInfo()
            assert await srcFont.getSources() == await dupedFont.getSources()
            assert await srcFont.getGlobalAxes() == await dupedFont.getGlobalAxes()
            assert await srcFont.getCustomData() == await dupedFont.getCustomData()
            for glyphName in glyphMap:
                assert await srcFont.getGlyph(glyphName) == await dupedFont.getGlyph(
                    glyphName
                )
