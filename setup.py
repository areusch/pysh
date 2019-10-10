from setuptools import setup


setup(
  name='pysh',
  version='0.0.1',
  packages=['pysh', 'pysh.ipython'],
  setup_requires=['tox-setuptools'],
  tests_require=['more-itertools < 6.0.0', 'six', 'tox'],
)
