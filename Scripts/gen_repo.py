#!/usr/bin/env python3
"""Regenerates flat APT repo index files (Packages, Packages.gz, Release)
and packages.json for the landing page from the debs/ directory."""
import gzip
import hashlib
import json
import os
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBS = os.path.join(ROOT, "debs")

ORIGIN = "thepoplive repo"
LABEL = "thepoplive repo"
SUITE = "stable"
ARCHS = "iphoneos-arm"
DESCRIPTION = "Tweaks and apps for legacy iOS 6-8 by thepoplive"

# package id -> source repository, shown as "Open in GitHub" on the site
GITHUB_REPOS = {
    "com.legacyui.tweak": "https://github.com/thepoplive/LegacyUI",
    "com.thepoplive.phonepod": "https://github.com/thepoplive/PhonePod",
}


def control_fields(deb):
    out = subprocess.check_output(["dpkg-deb", "-f", deb]).decode()
    fields = {}
    key = None
    for line in out.splitlines():
        if line.startswith(" ") or line.startswith("\t"):
            if key:
                fields[key] += "\n" + line.strip()
        elif ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.strip()
    return fields


def digest(path, fn):
    h = fn()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


deb_files = sorted(f for f in os.listdir(DEBS) if f.endswith(".deb"))
packages_entries = []
catalog = []

for name in deb_files:
    path = os.path.join(DEBS, name)
    fields = control_fields(path)
    size = os.path.getsize(path)
    entry = dict(fields)
    entry["Filename"] = "debs/" + name
    entry["Size"] = str(size)
    entry["MD5sum"] = digest(path, hashlib.md5)
    entry["SHA256"] = digest(path, hashlib.sha256)

    order = ["Package", "Name", "Version", "Architecture", "Description",
             "Maintainer", "Section", "Depends", "Filename", "Size",
             "MD5sum", "SHA256"]
    lines = ["%s: %s" % (k, entry[k]) for k in order if k in entry]
    # Any extra fields not covered above.
    for k in entry:
        if k not in order:
            lines.append("%s: %s" % (k, entry[k]))
    packages_entries.append("\n".join(lines))

    catalog.append({
        "package": entry.get("Package", ""),
        "name": entry.get("Name", entry.get("Package", "")),
        "version": entry.get("Version", ""),
        "description": entry.get("Description", "").split("\n")[0],
        "section": entry.get("Section", "Tweaks"),
        "filename": entry.get("Filename", ""),
        "size": size,
    })
    github_url = GITHUB_REPOS.get(entry.get("Package", ""))
    if github_url:
        catalog[-1]["github"] = github_url

packages_data = "\n".join(packages_entries) + "\n"
with open(os.path.join(ROOT, "Packages"), "w") as f:
    f.write(packages_data)
with gzip.open(os.path.join(ROOT, "Packages.gz"), "wb") as f:
    f.write(packages_data.encode())
with open(os.path.join(ROOT, "packages.json"), "w") as f:
    json.dump({"packages": catalog}, f, indent=2)

index_files = ["Packages", "Packages.gz"]
release_lines = [
    "Origin: %s" % ORIGIN,
    "Label: %s" % LABEL,
    "Suite: %s" % SUITE,
    "Codename: %s" % SUITE,
    "Version: 1.0",
    "Architectures: %s" % ARCHS,
    "Description: %s" % DESCRIPTION,
    "Date: %s" % time.strftime("%a, %d %b %Y %H:%M:%S %z"),
]

for algo, fn in (("MD5Sum", hashlib.md5), ("SHA1", hashlib.sha1), ("SHA256", hashlib.sha256)):
    release_lines.append(algo + ":")
    for name in index_files:
        p = os.path.join(ROOT, name)
        release_lines.append(" %s %8d %s" % (digest(p, fn), os.path.getsize(p), name))

with open(os.path.join(ROOT, "Release"), "w") as f:
    f.write("\n".join(release_lines) + "\n")

print("Generated: Packages (%d bytes), Packages.gz, Release, packages.json (%d packages)"
      % (len(packages_data), len(catalog)))