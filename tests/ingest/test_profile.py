from selfware.ingest import profile


def test_read_profile_returns_text(tmp_path):
    path = tmp_path / "profile.txt"
    path.write_text("This text is a test\n", encoding="utf-8")

    assert profile.read_profile(path) == "This text is a test"


def test_read_profile_strips_each_line(tmp_path):
    path = tmp_path / "profile.txt"
    path.write_text("  Diana  \n", encoding="utf-8")

    assert profile.read_profile(path) == "Diana"


def test_read_profile_keeps_utf8(tmp_path):
    path = tmp_path / "profile.txt"
    path.write_text("Ingeniería, señal\n", encoding="utf-8")

    assert profile.read_profile(path) == "Ingeniería, señal"


def test_read_profile_empty_file(tmp_path):
    path = tmp_path / "profile.txt"
    path.write_text("", encoding="utf-8")

    assert profile.read_profile(path) == ""
