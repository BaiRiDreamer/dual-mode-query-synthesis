"""Setup script for dual-mode-query-synthesis."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="dual-mode-query-synthesis",
    version="1.0.0",
    author="daVinci-Agency Research Team",
    description="Dual-mode query synthesis for PR chain trajectory generation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/GAIR/dual-mode-query-synthesis",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "dual-mode-query=cli.dual_mode_query_constructor_cli:main",
        ],
    },
)
