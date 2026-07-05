def schema_matcher(state):
    """
    统一 clean_data 格式
    """

    clean = state.get("clean_data", {})

    state["clean_data"] = {
        "student": clean.get("student"),
        "major": clean.get("major"),
        "course": clean.get("course")
    }

    print("✔ schema_matcher完成")

    return state