from setuptools import setup, find_packages

setup(
    name='django-rest-offlinesync',

    version='0.10.0',

    description='Offline Data Synchronization for Django REST Framework',

    url='https://github.com/vsemionov/django-rest-offlinesync',

    author='Victor Semionov',
    author_email='vsemionov@gmail.com',

    license='MIT',

    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries',
    ],

    keywords='offline data synchronization django rest python',

    packages=find_packages(),

    install_requires=[
        'Django',
        'djangorestframework',
    ],
)
