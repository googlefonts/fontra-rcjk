# fontra-rcjk
Fontra plug-in with [django-robocjk](https://github.com/googlefonts/django-robo-cjk) support and .rcjk file format support


# How to test code changes made in fontra which effects fontra-rjck
Let's imagine you have made some changes within fontra, which may have an impact to fontra-rcjk as well, eg. code refactoring. But the new code is not merged, yet, because we need to test it first.
The challenging part is, that we cannot add a specific branch to requirements-dev.txt, sadly.

1. Go to your local fontra folder/repo
2. Checkout the needed fontra branch into your current venv
2. Go to you fontra-rcjk folder/repo
3. Install the required fontra branch via: `pip install -e ../fontra/`
4. Run `pytest`

Please keep in mind the *_fs backend has some unit tests. The mysql one does not, so we need to be super careful there.


# How to run a rcjk project

1. Start fontra like this: `fontra rcjk robocjk.black-foundry.com`
2. Open the `http://localhost:8000/`
3. Then use your robocjk login credentials to log in.
4. Click a project.
