import json
import pathlib
import re
import shutil
import subprocess
from functools import cache
from urllib.parse import urlparse

gitHashPattern = re.compile(r"(^[0-9a-f]{7}$)|(^[0-9a-f]{40}$)")


@cache
def getRepoHeadCommitHash(repoURL):
    result = subprocess.run(
        f"git ls-remote {gitURL}",
        check=True,
        shell=True,
        capture_output=True,
        encoding="utf-8",
    )

    headCommitHash = result.stdout.split()[0]
    assert gitHashPattern.match(headCommitHash) is not None
    return headCommitHash


repoDir = pathlib.Path(__file__).resolve().parent.parent

rootPackagePath = repoDir / "package.json"
rootPackageLockPath = repoDir / "package-lock.json"
rootNodeModulesPath = repoDir / "node_modules"

rootPackage = json.loads(rootPackagePath.read_text(encoding="utf-8"))

for workspace in rootPackage["workspaces"]:
    workspaceNodeModulesPath = repoDir / workspace / "node_modules"
    if workspaceNodeModulesPath.is_dir():
        shutil.rmtree(workspaceNodeModulesPath)

    workspacePackagePath = repoDir / workspace / "package.json"
    workspacePackage = json.loads(workspacePackagePath.read_text(encoding="utf-8"))

    newDeps = {}
    for key, depURL in workspacePackage["dependencies"].items():
        url = urlparse(depURL)
        if (
            url.hostname != "gitpkg.vercel.app"
            or gitHashPattern.match(url.query) is None
        ):
            newDeps[key] = depURL
            continue

        project, repo = url.path.split("/")[1:3]
        gitURL = f"https://github.com/{project}/{repo}.git"

        headCommitHash = getRepoHeadCommitHash(gitURL)
        url = url._replace(query=headCommitHash)
        newDeps[key] = url.geturl()

    workspacePackage["dependencies"] = newDeps
    workspacePackagePath.write_text(
        json.dumps(workspacePackage, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

if rootPackageLockPath.is_file():
    # We need to build package-lock.json from scratch, or else
    rootPackageLockPath.unlink()

if rootNodeModulesPath.is_dir():
    shutil.rmtree(rootNodeModulesPath)

subprocess.run("npm install --prefer-deduped", check=True, shell=True)
