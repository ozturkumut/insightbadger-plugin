import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "engine", "skills", "dig-deep", "scripts"))
sys.path.insert(0, HERE)

import pytest  # noqa: E402

FIX = os.path.join(HERE, "fixtures")


@pytest.fixture(scope="session", autouse=True)
def fixtures_exist():
    if not os.path.exists(os.path.join(FIX, "qualtrics.csv")):
        import make_fixtures
        make_fixtures.main()


@pytest.fixture(scope="session")
def qualtrics():
    from insight_badger.loading import load_survey
    return load_survey(os.path.join(FIX, "qualtrics.csv"))


@pytest.fixture(scope="session")
def q_profile(qualtrics):
    from insight_badger.detect import build_profile
    return build_profile(qualtrics)


@pytest.fixture(scope="session")
def q_results(qualtrics, q_profile):
    from insight_badger.analyze import run
    return run(qualtrics, q_profile, compare=["Q3"])
