"""
DRPG: Differentiable Robust Price Game for Energy Dispatch
Setup script for package installation
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the long description from README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

# Core dependencies (production)
INSTALL_REQUIRES = [
    'numpy>=1.24.0,<2.0.0',
    'scipy>=1.10.0,<2.0.0',
    'cvxpy>=1.4.0',
    'osqp>=0.6.2',
    'scs>=3.2.0',
    'pandas>=2.0.0,<3.0.0',
    'matplotlib>=3.7.0,<4.0.0',
    'seaborn>=0.12.0,<1.0.0',
    'statsmodels>=0.14.0',
    'pyyaml>=6.0',
    'tqdm>=4.65.0',
    'colorlog>=6.7.0'
]

# Development dependencies
DEV_REQUIRES = [
    'pytest>=7.3.0',
    'pytest-cov>=4.1.0',
    'black>=23.3.0',
    'flake8>=6.0.0',
    'mypy>=1.3.0',
    'isort>=5.12.0',
    'sphinx>=6.0.0',
    'sphinx-rtd-theme>=1.2.0'
]

# Optional dependencies
EXTRAS_REQUIRE = {
    'dev': DEV_REQUIRES,
    'ieee': ['pandapower>=2.13.0'],  # For IEEE test cases
    'jupyter': ['jupyter>=1.0.0', 'notebook>=6.5.0', 'ipywidgets>=8.0.0'],
    'profiling': ['memory-profiler>=0.61.0', 'line-profiler>=4.0.0'],
    'all': DEV_REQUIRES + ['pandapower>=2.13.0', 'jupyter>=1.0.0', 'memory-profiler>=0.61.0']
}

setup(
    name='drpg',
    version='1.0.0',
    author='[Your Name]',
    author_email='[your.email@domain.com]',
    description='Differentiable Robust Price Game for Energy Dispatch',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/[username]/drpg',
    project_urls={
        'Bug Tracker': 'https://github.com/[username]/drpg/issues',
        'Documentation': 'https://drpg.readthedocs.io',
        'Source Code': 'https://github.com/[username]/drpg',
    },
    packages=find_packages(exclude=['tests', 'tests.*', 'archive', 'archive.*']),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Mathematics',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.9',
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    entry_points={
        'console_scripts': [
            'drpg-run=experiments.run_experiment:main',  # CLI for running experiments
        ],
    },
    include_package_data=True,
    package_data={
        '': ['*.yaml', '*.yml', '*.json', '*.md'],
        'config': ['ieee_systems/*.json'],
    },
    zip_safe=False,
    keywords='robust optimization, energy dispatch, envelope theorem, price game, convex optimization',
)
