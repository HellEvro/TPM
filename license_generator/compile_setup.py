"""
Setup для компиляции license_checker.py в .pyd
"""

from setuptools import setup, Extension
from Cython.Build import cythonize
from pathlib import Path

# Находим исходный файл
source_file = Path('source/license_checker.py')

if not source_file.exists():
    raise FileNotFoundError(f"Source file not found: {source_file}")

extensions = [
    Extension(
        'license_checker',
        [str(source_file)],
        language='c',
    )
]

setup(
    name='license_checker',
    version='1.0.0',
    description='License checker (compiled)',
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            'language_level': "3",
            'embedsignature': False,
            'boundscheck': False,
            'wraparound': False,
        }
    ),
    zip_safe=False,
)

