def read_profile(profile_path):
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = "".join(line.strip() for line in f)
    return profile_data
