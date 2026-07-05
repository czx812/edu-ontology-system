def get_mock_state():
    return {
        "file_path": "demo.pdf",
        "raw_text": "张三是计算机系学生，学习人工智能",

        "clean_data": {
            "student": "张三",
            "major": "计算机系",
            "course": "人工智能"
        },

        "ontology": {
            "classes": ["Student", "Department", "Course", "Student"],
            "relations": [
                {"subject": "张三", "type": "belongsTo", "object": "计算机系"},
                {"subject": "张三", "type": "studies", "object": "人工智能"},
                {"subject": "张三", "type": "belongsTo", "object": "计算机系"}
            ]
        },

        "owl_file": ""
    }