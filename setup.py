#!/usr/bin/env python
# std imports,
import subprocess
import sys
import os

# 3rd-party
import setuptools
import setuptools.command.develop
import setuptools.command.test

here = os.path.dirname(__file__)


class SetupDevelop(setuptools.command.develop.develop):
    def run(self):
        # ensure a virtualenv is loaded,
        assert os.getenv('VIRTUAL_ENV'), 'You should be in a virtualenv'
        # ensure tox is installed
        subprocess.check_call(('pip', 'install', 'tox'))
        # install development egg-link
        setuptools.command.develop.develop.run(self)


class SetupTest(setuptools.command.test.test):
    def run(self):
        self.spawn(('tox',))


def main():
    extra = {
        'install_requires': [
            'wcwidth>=0.1.0',
        ]
    }
    if sys.version_info < (2, 7,):
        extra['install_requires'].extend(['ordereddict>=1.1'])

    setuptools.setup(
        name='blessed',
        version='1.9.4',
        description="A feature-filled fork of Erik Rose's blessings project",
        long_description=open(os.path.join(here, 'README.rst')).read(),
        author='Jeff Quast',
        author_email='contact@jeffquast.com',
        license='MIT',
        packages=['blessed', 'blessed.tests'],
        url='https://github.com/jquast/blessed',
        include_package_data=True,
        test_suite='blessed.tests',
        classifiers=[
            'Intended Audience :: Developers',
            'Natural Language :: English',
            'Development Status :: 5 - Production/Stable',
            'Environment :: Console',
            'Environment :: Console :: Curses',
            'License :: OSI Approved :: MIT License',
            'Operating System :: POSIX',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 2.6',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.2',
            'Programming Language :: Python :: 3.3',
            'Programming Language :: Python :: 3.4',
            'Topic :: Software Development :: Libraries',
            'Topic :: Software Development :: User Interfaces',
            'Topic :: Terminals'
        ],
        keywords=['terminal', 'sequences', 'tty', 'curses', 'ncurses',
                  'formatting', 'style', 'color', 'console', 'keyboard',
                  'ansi', 'xterm'],
        cmdclass={'develop': SetupDevelop,
                  'test': SetupTest},
        **extra
    )

if __name__ == '__main__':
    main()
