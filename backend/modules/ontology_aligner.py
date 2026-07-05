def ontology_aligner(state):
    ontology = state.get("ontology", {})

    # classes去重
    classes = list(set(ontology.get("classes", [])))

    # relations去重
    seen = set()
    relations = []

    for r in ontology.get("relations", []):
        key = (r["subject"], r["type"], r["object"])
        if key not in seen:
            seen.add(key)
            relations.append(r)

    state["ontology"] = {
        "classes": classes,
        "relations": relations
    }

    print("✔ ontology_aligner完成")

    return state