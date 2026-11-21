"""Environment specs for the SWE-bench repositories Benchy runs, without Docker.

Adapted from SWE-bench's harness constants (swebench 3.0.17, `harness/constants/python.py`,
MIT License, Copyright (c) 2023 Carlos E Jimenez, John Yang, Alexander Wettig, Shunyu Yao,
Kexin Pei, Ofir Press, Karthik R Narasimhan). Changes from the original:

- No conda, apt or shell: each environment is a `uv venv` with the same Python version and pip
  pins. Steps that need system packages (apt-get) make that repository version unsupported.
- `sed` pre-install edits become literal, first-match-per-line replacements (`SetupEdit`).
- The project itself is installed *non-editable* from its environment commit, so dependencies,
  entry points and package metadata exist. Tests then run with `python -m pytest` from the task
  workspace, which puts the workspace first on `sys.path`, so the code under test is always the
  workspace's own copy (every supported repository has a flat package layout).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SetupEdit:
    """Replace the first `old` on each line of `path` with `new` (what `sed 's/old/new/'` does)."""

    path: str
    old: str
    new: str


@dataclass(frozen=True)
class EnvSpec:
    python: str
    pip: tuple[str, ...] = ()
    install: str = ""  # "" = do not install the project; "." or ".[test]" = pip install that
    requirements: tuple[str, ...] = ()  # requirement files inside the repository, installed with -r
    edits: tuple[SetupEdit, ...] = field(default_factory=tuple)
    # Optional test dependencies SWE-bench got from a conda environment file, installed last with
    # the `pip` pins as constraints (only those that install from PyPI without system libraries).
    optional: tuple[str, ...] = ()

    def key_parts(self) -> tuple:
        return (self.python, self.pip, self.install, self.requirements, self.edits, self.optional)


class Unsupported(ValueError):
    """This repository version cannot be rebuilt without Docker or system packages."""


def _sphinx_edits(version: str) -> tuple[SetupEdit, ...]:
    if version not in {"3.0", "3.1", "3.2", "3.3", "3.4", "3.5", "4.0", "4.1", "4.2", "4.3", "4.4"}:
        return ()
    edits = [
        SetupEdit("setup.py", "Jinja2>=2.3", "Jinja2<3.0"),
        SetupEdit("setup.py", "sphinxcontrib-applehelp", "sphinxcontrib-applehelp<=1.0.7"),
        SetupEdit("setup.py", "sphinxcontrib-devhelp", "sphinxcontrib-devhelp<=1.0.5"),
        SetupEdit("setup.py", "sphinxcontrib-qthelp", "sphinxcontrib-qthelp<=1.0.6"),
        SetupEdit("setup.py", "alabaster>=0.7,<0.8", "alabaster>=0.7,<0.7.12"),
        SetupEdit("setup.py", "'packaging',", "'packaging', 'markupsafe<=2.0.1',"),
    ]
    if version in {"4.2", "4.3", "4.4"}:
        edits += [
            SetupEdit(
                "setup.py",
                "sphinxcontrib-htmlhelp>=2.0.0",
                "sphinxcontrib-htmlhelp>=2.0.0,<=2.0.4",
            ),
            SetupEdit(
                "setup.py",
                "sphinxcontrib-serializinghtml>=1.1.5",
                "sphinxcontrib-serializinghtml>=1.1.5,<=1.1.9",
            ),
        ]
    elif version == "4.1":
        # SWE-bench tries the ">=" form first and falls back to the bare name; the replacement
        # below gives the same result for both spellings.
        edits += [
            SetupEdit(
                "setup.py", "sphinxcontrib-htmlhelp>=2.0.0", "sphinxcontrib-htmlhelp>=2.0.0,<=2.0.4"
            ),
            SetupEdit(
                "setup.py",
                "sphinxcontrib-serializinghtml>=1.1.5",
                "sphinxcontrib-serializinghtml>=1.1.5,<=1.1.9",
            ),
        ]
    else:
        edits += [
            SetupEdit("setup.py", "sphinxcontrib-htmlhelp", "sphinxcontrib-htmlhelp<=2.0.4"),
            SetupEdit(
                "setup.py", "sphinxcontrib-serializinghtml", "sphinxcontrib-serializinghtml<=1.1.9"
            ),
        ]
    return tuple(edits)


XARRAY_PINS = (
    "numpy==1.23.0",
    "packaging==23.1",
    "pandas==1.5.3",
    "pytest==7.4.0",
    "python-dateutil==2.8.2",
    "pytz==2023.3",
    "six==1.16.0",
    "scipy==1.11.1",
    "setuptools==68.0.0",
    "dask==2022.8.1",
)

# From xarray's ci/requirements/environment.yml, minus packages that need system libraries or
# have no wheels (cartopy, cdms2, cfgrib, iris, rasterio, pseudonetcdf, pydap) and CI-only tools.
XARRAY_OPTIONAL = (
    "bottleneck",
    "cftime",
    "distributed",
    "h5netcdf",
    "h5py",
    "hypothesis",
    "matplotlib",
    "nc-time-axis",
    "netcdf4",
    "numba",
    "numbagg",
    "numexpr",
    "pint",
    "pooch",
    "pytest-env",
    "seaborn",
    "sparse",
    "toolz",
    "zarr<3",
)


def spec_for(repo: str, version: str) -> EnvSpec:
    """The environment for one repository version, or `Unsupported` with the reason."""
    spec = _spec_for(repo, version)
    if not any(
        p.split("<")[0].split("=")[0].strip() == "setuptools" and p != "setuptools"
        for p in spec.pip
    ):
        # SWE-bench's images (2024) had a setuptools that still ships pkg_resources, which older
        # sphinx and pylint import at runtime; current setuptools no longer does.
        pip = tuple(p for p in spec.pip if p != "setuptools") + ("setuptools<70",)
        spec = EnvSpec(spec.python, pip, spec.install, spec.requirements, spec.edits, spec.optional)
    return spec


def _spec_for(repo: str, version: str) -> EnvSpec:
    if repo == "sympy/sympy":
        # SWE-bench runs sympy's own bin/test; its test files are plain pytest functions.
        return EnvSpec(python="3.9", pip=("mpmath==1.3.0", "pytest"))
    if repo == "sphinx-doc/sphinx":
        if version in {"7.2", "7.3", "7.4", "8.0", "8.1"}:
            raise Unsupported("needs graphviz from the system package manager")
        # docutils 0.22 (2025) dropped the `roman` module old sphinx imports; SWE-bench's images
        # (2024) had an older docutils.
        return EnvSpec(
            python="3.9",
            pip=("Jinja2==3.0.3", "docutils<0.22"),
            install=".[test]",
            edits=_sphinx_edits(version),
        )
    if repo == "pylint-dev/pylint":
        if version == "2.8":
            raise Unsupported("needs libenchant from the system package manager")
        major = int(version.split(".")[0])
        pip: tuple[str, ...] = ("astroid==3.0.0a6", "setuptools") if major >= 3 else ()
        return EnvSpec(python="3.9", pip=pip, install=".", requirements=("requirements_test.txt",))
    if repo == "pydata/xarray":
        return EnvSpec(python="3.10", pip=XARRAY_PINS, install=".", optional=XARRAY_OPTIONAL)
    raise Unsupported(f"{repo} is not in Benchy's SWE-bench suite")


SUPPORTED_REPOS = ("sympy/sympy", "sphinx-doc/sphinx", "pylint-dev/pylint", "pydata/xarray")
EXCLUDED_REPOS = {
    "django/django": "runs its own test runner (tests/runtests.py), not pytest",
    "matplotlib/matplotlib": "needs a C/C++ compiler and system libraries",
    "scikit-learn/scikit-learn": "needs a C/C++ compiler (Cython extensions)",
    "astropy/astropy": "needs a C compiler (C extensions)",
    "pytest-dev/pytest": "src layout: a workspace run would import the installed copy",
    "psf/requests": "its tests call httpbin.org over the network",
    "mwaskom/seaborn": "too few tasks (2) to be worth a separate environment",
    "pallets/flask": "too few tasks (1); src layout",
}
