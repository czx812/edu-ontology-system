def generate_owl(state):
    ontology = state.get("ontology", {})

    owl_text = ""

    owl_text += "### Classes ###\n"
    for c in ontology.get("classes", []):
        owl_text += f"Class: {c}\n"

    owl_text += "\n### Relations ###\n"
    for r in ontology.get("relations", []):
        owl_text += f"{r['subject']} {r['type']} {r['object']}\n"

    file_path = "output.owl"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(owl_text)

    state["owl_file"] = file_path

    print("✔ OWL生成完成:", file_path)

    return state