from setuptools import setup

setup(
    name='alpakka',
    version='0.1.dev',
    description="Cutest YANG Eater alive",

    install_requires=['pyang', 'path.py', 'ipython', 'orderedset'],

    packages=[
        'alpakka',
        'alpakka.pyang_plugins',
        'alpakka.wrapper',
        'alpakka.wools',
        'alpakka.templates',
    ],
    entry_points={
        'console_scripts': ['alpakka=alpakka:run'],
    },
)
