from setuptools import setup

setup(
    name='alpakka',
    version='0.1.dev',
    description="Akka code stub generator from YANG models via pyang.",

    install_requires=['pyang', 'jinja2', 'path.py'],

    packages=[
        'alpakka',
        'alpakka.pyang_plugins',
    ],
    entry_points={
        'console_scripts': ['alpakka=alpakka:run'],
    },
)
