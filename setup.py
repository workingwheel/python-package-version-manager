from setuptools import setup, find_packages

setup(
    name="python-package-version-manager",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "rich",
        "inquirer",
        "packaging"
    ],
    entry_points={
        'console_scripts': [
            'pkgversion=check_versions:main',
        ],
    },
    author="workingwheel",
    description="A Python utility for managing package versions with an interactive CLI interface",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/workingwheel/python-package-version-manager",
    classifiers=[
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.12",
)
