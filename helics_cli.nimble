# Package

version       = "0.2.1"
author        = "Dheepak Krishnamurthy"
description   = "HELICS command line interface"
license       = "MIT"
binDir        = "bin"
packageName   = "helics_cli"
bin           = @[packageName]

# Dependencies

requires "nim >= 1.2.0"
requires "cligen"
requires "shlex"
requires "jester"
# requires "https://github.com/GMLC-TDC/helics.nim"

import strutils
import os
import strformat

before build:
  rmDir(binDir)

after build:
  let cli = packageName
  mvFile binDir / cli, binDir / cli.replace("_cli", "")

task clean, "Clean project":
  rmDir(nimCacheDir())

task archive, "Create archived assets":
  exec "nimble run"
  let cli = packageName.replace("_cli", "")
  let assets = &"{cli}_v{version}_{buildOS}"
  let dist = "dist"
  let dist_dir = dist/assets
  rmDir dist_dir
  mkDir dist_dir
  cpDir binDir, dist_dir/binDir
  cpFile "LICENSE", dist_dir/"LICENSE"
  cpFile "README.md", dist_dir/"README.md"
  withDir dist:
    when buildOS == "windows":
      exec &"7z a {assets}.zip {assets}"
    else:
      exec &"""chmod +x ./{assets / binDir / cli}"""
      exec &"tar czf {assets}.tar.gz {assets}"

task changelog, "Create a changelog":
  exec("./scripts/changelog.nim")

task debug, "Clean and build debug":
  exec "nimble clean"
  exec "nimble build"

task release, "Clean and build release":
  exec "nimble clean"
  exec "nimble build -d:release --opt:size -Y"