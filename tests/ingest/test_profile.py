import selfware.ingest.profile as profile

def create_empty_file(path, text):
    pass

def process_profile():
    example_string = "This text is a test"
    text = profile.read_profile(file)

    assert text == example_string

def process_empty_file():
    text = profile.read_profile(file)

    assert text is not None
    assert len(text) == 0