def read_profile(profile_path):
    with open(profile_path, "r", encoding="utf-8") as f:
        text = f.read().strip()
    return text
