"""Nox configuration."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from textwrap import dedent
import glob

import nox

try:
    from nox_poetry import Session, session
except ImportError:
    message = f"""\
    Nox failed to import the 'nox-poetry' package.
    Please install it using the following command:
    {sys.executable} -m pip install nox-poetry"""
    raise SystemExit(dedent(message)) from None

package = "singer_sdk"
python_versions = ["3.11", "3.10", "3.9", "3.8", "3.7"]
main_python_version = "3.10"
locations = "singer_sdk", "tests", "noxfile.py", "docs/conf.py"
nox.options.sessions = (
    "mypy",
    "tests",
    "doctest",
    "test_cookiecutter"
)
test_dependencies = [
    "coverage[toml]",
    "pytest",
    "pytest-snapshot",
    "pytest-durations",
    "freezegun",
    "pandas",
    "pyarrow",
    "requests-mock",
    # Cookiecutter tests
    "black",
    "cookiecutter",
    "PyYAML",
    "darglint",
    "flake8",
    "flake8-annotations",
    "flake8-docstrings",
    "mypy",
]


@session(python=python_versions)
def mypy(session: Session) -> None:
    """Check types with mypy."""
    args = session.posargs or ["singer_sdk"]
    session.install(".")
    session.install(
        "mypy",
        "pytest",
        "importlib-resources",
        "sqlalchemy2-stubs",
        "types-jsonschema",
        "types-python-dateutil",
        "types-pytz",
        "types-requests",
        "types-simplejson",
        "types-PyYAML",
    )
    session.run("mypy", *args)
    if not session.posargs:
        session.run("mypy", f"--python-executable={sys.executable}", "noxfile.py")


@session(python=python_versions)
def tests(session: Session) -> None:
    """Execute pytest tests and compute coverage."""
    session.install(".[s3]")
    session.install(*test_dependencies)

    try:
        session.run(
            "coverage",
            "run",
            "--parallel",
            "-m",
            "pytest",
            "-v",
            "--durations=10",
            *session.posargs,
            env={
                "SQLALCHEMY_WARN_20": "1",
            },
        )
    finally:
        if session.interactive:
            session.notify("coverage", posargs=[])


@session(python=main_python_version)
def update_snapshots(session: Session) -> None:
    """Update pytest snapshots."""
    args = session.posargs or ["-m", "snapshot"]

    session.install(".")
    session.install(*test_dependencies)
    session.run("pytest", "--snapshot-update", *args)


@session(python=python_versions)
def doctest(session: Session) -> None:
    """Run examples with xdoctest."""
    if session.posargs:
        args = [package, *session.posargs]
    else:
        args = [package]
        if "FORCE_COLOR" in os.environ:
            args.append("--xdoctest-colored=1")

    session.install(".")
    session.install("pytest", "xdoctest[colors]")
    session.run("pytest", "--xdoctest", *args)


@session(python=main_python_version)
def coverage(session: Session) -> None:
    """Generate coverage report."""
    args = session.posargs or ["report", "-m"]

    session.install("coverage[toml]")

    if not session.posargs and any(Path().glob(".coverage.*")):
        session.run("coverage", "combine")

    session.run("coverage", *args)


@session(name="docs", python=main_python_version)
def docs(session: Session) -> None:
    """Build the documentation."""
    args = session.posargs or ["docs", "build", "-W"]
    if not session.posargs and "FORCE_COLOR" in os.environ:
        args.insert(0, "--color")

    session.install(".[docs]")

    build_dir = Path("build")
    if build_dir.exists():
        shutil.rmtree(build_dir)

    session.run("sphinx-build", *args)


@session(name="docs-serve", python=main_python_version)
def docs_serve(session: Session) -> None:
    """Build the documentation."""
    args = session.posargs or [
        "--open-browser",
        "--watch",
        ".",
        "--ignore",
        "**/.nox/*",
        "docs",
        "build",
        "-W",
    ]
    session.install(".[docs]")

    build_dir = Path("build")
    if build_dir.exists():
        shutil.rmtree(build_dir)

    session.run("sphinx-autobuild", *args)


@session(python=python_versions)
def test_cookiecutter(session: Session) -> None:
    """Uses the tap template to build an empty cookiecutter, and runs the lint task on the created test project."""
    args = session.posargs or [
        "./cookiecutter/tap-template",
        "./e2e-tests/cookiecutters/tap-rest-api_key-github.json"
    ]
    if len(args) == 1:
        print("ERROR:" + args[0])
        return 0

    cc_build_path = "/tmp"
    tap_template = os.path.abspath(args[0])
    replay_file = os.path.abspath(args[1])

    if not os.path.exists(tap_template):
        print("Tap template folder not found")
        return 0

    if not os.path.isfile(replay_file):
        print("Replay file not found")
        return 0

    sdk_dir = os.path.dirname(os.path.dirname(tap_template))
    cc_output_dir = os.path.basename(args[1]).replace(".json", "")
    cc_test_output = (cc_build_path + "/" + cc_output_dir)

    if os.path.exists(cc_test_output):
        session.run("rm", "-fr", cc_test_output, external=True)

    session.install(".")
    session.install("cookiecutter", "pythonsed")

    session.run("cookiecutter", "--replay-file", replay_file,
                tap_template, "-o", cc_build_path)
    os.chdir(cc_test_output)
    print(os.getcwd())

    session.run("pythonsed", "-i.bak",
                "s|singer-sdk =.*|singer-sdk = \{ path = \"" + sdk_dir + "\", develop = true \}|", "pyproject.toml")
    session.run("poetry", "lock", external=True)
    session.run("poetry", "install", external=True)

    for path in glob.glob(f'{os.getcwd()}/*', recursive=True):
        if os.path.basename(path).startswith("tap") or os.path.basename(path).startswith("target"):
            library_name = os.path.basename(path)

    session.run("poetry", "run", "black", library_name, external=True)
    session.run("poetry", "run", "isort", library_name, external=True)
    session.run("poetry", "run", "flake8", library_name, external=True)
    session.run("poetry", "run", "mypy", library_name, external=True)

    if len(args) < 3 or int(args[2]) == 1:
        session.run("poetry", "run", "tox", "-e", "lint", external=True)
    
