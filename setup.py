from setuptools import setup

setup(name='parse_apache_configs',
      version="1.0",
      description="A python module to parse apache config files.",
      url='https://github.com/daladim/parse_apache_configs',
      download_url = 'https://github.com/daladim/parse_apache_configs/tarball/1.0',
      author='Miguel Alex Cantu and Jérôme Froissart',
      author_email='software@froissart.eu',
      packages=['parse_apache_configs'],
      install_requires=[
          'pyparsing',
      ],
      zip_safe=False)
