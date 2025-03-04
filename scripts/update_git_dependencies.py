import json
import pathlib
import re
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

rootPackage = json.loads(rootPackagePath.read_text(encoding="utf-8"))

for workspace in rootPackage["workspaces"]:
    unwantedNodeModulesPath = repoDir / workspace / "node_modules"
    assert (
        not unwantedNodeModulesPath.is_dir()
    ), f"unexpected node_modules folder ({unwantedNodeModulesPath.relative_to(repoDir)})"

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


subprocess.run("npm install --prefer-deduped", check=True, shell=True)
