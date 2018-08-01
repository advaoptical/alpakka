from setuptools import setup


setup(
    name='alpakka',
    description="Cutest YANG Eater alive",

    author="ADVA Optical Networking",
    maintainer="Thomas Szyrkowiec",
    maintainer_email="tszyrkowiec@advaoptical.com",

    license="Apache License 2.0",

    setup_requires=open('requirements.setup.txt'),
    install_requires=['pyang', 'path.py', 'ipython'],

    use_scm_version={'local_scheme': lambda _: ''},

    packages=[
        'alpakka',
        'alpakka.pyang_plugins',
        'alpakka.wrapper',
        'alpakka.wools',
    ],
    entry_points={
        'console_scripts': ['alpakka=alpakka:run'],
    },

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Telecommunications Industry',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Software Development',
        'Topic :: Software Development :: Code Generators',
        'Topic :: Utilities',
    ],
    keywords=[
        'alpakka', 'yang', 'pyang', 'wool', 'wools',
    ],
)
