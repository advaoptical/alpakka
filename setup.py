from setuptools import setup

setup(
    name='alpakka',
    version='0.1.dev',
    description="Cutest YANG Eater alive",

    install_requires=['pyang', 'path.py', 'ipython'],

    packages=[
        'alpakka',
        'alpakka.pyang_plugins',
        'alpakka.wrapper',
        'alpakka.wools',
    ],
    entry_points={
        'console_scripts': ['alpakka=alpakka:run'],
    },
)
