"""Nox configuration."""

import os
import shutil
import sys
from pathlib import Path
from textwrap import dedent
import os
import re

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
locations =  "noxfile.py"
nox.options.sessions = (
    "do_something",
    #"do_another"
)
cc_build_path = "/tmp"


test_dependencies = [
    "cookiecutter",
]

@session(python=main_python_version)
def do_something(session: Session) -> None:
    """Uses the tap template to build an empty cookiecutter, and runs the lint task on the created test project."""
    args = session.posargs
    
    session.run("pip", "install", "virtualenv")
    session.run("pip", "install", "nox")
    session.run("pip", "install", "cookiecutter")
    session.run("pip", "install", "pythonsed")
    session.run("pip", "install", "poetry")

    if not (session.posargs and len(session.posargs) == 2):
        print("INPUT IS WRONG!!!")
        return 0

    tap_template = os.path.abspath(session.posargs[0])
    replay_file = os.path.abspath(session.posargs[1])
    sdk_dir = os.path.dirname(os.path.dirname(tap_template))
    cc_output_dir = os.path.basename(session.posargs[1]).replace("json", "")
    cc_test_output = (cc_build_path + "/" + cc_output_dir).replace(".","")

    print("START")
    print(os.path.exists(cc_test_output))
    if os.path.exists(cc_test_output):
        session.run("rm", "-fr", cc_test_output)
    print(os.path.exists(cc_test_output))
    print("FINSH")


    print(os.getcwd())
    
    session.run("cookiecutter", "--replay-file", replay_file,
                tap_template, "-o", cc_build_path)
    print(os.path.exists(cc_test_output))
    current_path = os.getcwd()
    print( current_path)
    os.chdir(cc_test_output)
    print(os.getcwd())
    session.run("pythonsed","-i.bak", "s|singer-sdk =.*|singer-sdk = \{ path = \"" + sdk_dir + "\", develop = true \}|", "pyproject.toml" )
    session.run("poetry", "lock")
    session.run("poetry", "install")

    library_name= "tap_rest_api_key_github"
    session.run("poetry", "run", "black", library_name)
    session.run("poetry","run", "isort", library_name)
    session.run("poetry","run", "flake8", library_name)
    session.run("poetry","run", "mypy", library_name)