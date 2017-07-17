from setuptools import setup

setup(
    name='alpakka',
    version='0.1.dev',
    description="Akka code stub generator from YANG models via pyang.",

    install_requires=['pyang', 'jinja2', 'path.py', 'pluggy>=0.4'],

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
