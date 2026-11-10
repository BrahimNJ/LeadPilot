import subprocess
import sys


def test_app_starts_without_loading_the_anthropic_sdk():
    # A fresh interpreter: in this test process other tests have already imported the SDK.
    code = "import sys, app.main; print('anthropic' in sys.modules)"

    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert result.stdout.strip() == "False"
