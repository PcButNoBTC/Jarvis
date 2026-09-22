from delivery import generate_project, validate_project, package_project


def test_static_site_delivery_generates_and_validates(tmp_path, monkeypatch):
    monkeypatch.setattr("delivery.DELIVERY_ROOT", tmp_path)
    project = {
        "id": "project-1",
        "business_name": "Acme Plumbing",
        "service_name": "AI Website",
        "website_url": "https://acme.example",
        "requirements": {
            "site_title": "Acme Plumbing",
            "phone": "555-0100",
            "email": "hello@acme.example",
            "primary_cta": "Request a quote",
            "services": ["Drain cleaning", "Water heaters"],
        },
    }
    result = generate_project(project)
    assert "site/index.html" in result["files"]
    assert validate_project(project)["passed"] is True
    archive = package_project(project)
    assert archive.exists()


def test_workflow_delivery_generates_activation_package(tmp_path, monkeypatch):
    monkeypatch.setattr("delivery.DELIVERY_ROOT", tmp_path)
    project = {
        "id": "project-2",
        "business_name": "Acme Dental",
        "service_name": "Appointment Automation",
        "requirements": {"dependencies": ["Calendar provider"]},
    }
    result = generate_project(project)
    assert "workflow.json" in result["files"]
    assert validate_project(project)["passed"] is True
