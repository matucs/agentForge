from app.agents.security_scan import scan_file, scan_files


def test_detects_aws_access_key_as_high_severity_blocking() -> None:
    content = 'AWS_KEY = "AKIAABCDEFGHIJKLMNOP"\n'
    findings = scan_file("config.py", content)
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].category == "aws_access_key"
    assert findings[0].blocking is True
    assert findings[0].line == 1


def test_detects_private_key_header() -> None:
    content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow...\n"
    findings = scan_file("id_rsa", content)
    assert any(f.category == "private_key_header" for f in findings)


def test_detects_hardcoded_api_key_assignment() -> None:
    content = 'api_key = "sk-abcdefghijklmnopqrstuvwx"\n'
    findings = scan_file("settings.py", content)
    assert any(f.category == "hardcoded_api_key_assignment" for f in findings)


def test_detects_eval_as_medium_severity_non_blocking() -> None:
    content = "result = eval(user_input)\n"
    findings = scan_file("handler.py", content)
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].category == "eval_usage"
    assert findings[0].blocking is False


def test_detects_shell_true_and_pickle_loads() -> None:
    content = "subprocess.run(cmd, shell=True)\ndata = pickle.loads(raw)\n"
    findings = scan_file("run.py", content)
    categories = {f.category for f in findings}
    assert categories == {"shell_true", "pickle_loads"}


def test_clean_file_produces_no_findings() -> None:
    content = "def add(a, b):\n    return a + b\n"
    assert scan_file("clean.py", content) == []


def test_scan_files_aggregates_across_multiple_files() -> None:
    files = {
        "a.py": 'API_KEY = "abcdefghijklmnopqrstuvwx1234"\n',
        "b.py": "def ok():\n    pass\n",
        "c.py": "eval('1+1')\n",
    }
    findings = scan_files(files)
    files_with_findings = {f.file for f in findings}
    assert files_with_findings == {"a.py", "c.py"}
