from __future__ import annotations

import json
import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

from service_adapters import build_plan

DELIVERY_ROOT = Path(os.getenv("LUMA_DELIVERY_ROOT", "/data/delivery"))

SERVICE_BLUEPRINTS: dict[str, dict[str, Any]] = {
    "AI Website": {"slug": "ai-website", "kind": "static_site", "acceptance": [
        "Production build/package exists", "Responsive layout is included",
        "Primary contact path is present", "Business details are populated from approved requirements",
        "Deployment and handoff instructions are included"]},
    "Lead Capture System": {"slug": "lead-capture", "kind": "lead_capture", "acceptance": [
        "Lead form is present", "Required fields are documented",
        "Lead destination is configured or explicitly marked pending",
        "Spam/abuse controls are documented", "Test submission instructions are included"]},
    "Appointment Automation": {"slug": "appointment-automation", "kind": "workflow", "acceptance": [
        "Booking workflow specification exists", "Reminder and follow-up steps are documented",
        "Calendar/provider dependency is explicit", "Activation checklist is included"]},
    "AI Receptionist": {"slug": "ai-receptionist", "kind": "workflow", "acceptance": [
        "Call handling specification exists", "Escalation rules are documented",
        "Business hours and contact details are captured", "Provider activation checklist is included"]},
    "Review Automation": {"slug": "review-automation", "kind": "workflow", "acceptance": [
        "Review request workflow exists", "Timing and follow-up rules are documented",
        "Destination/review profile dependency is explicit", "Activation checklist is included"]},
    "Video Walkthrough": {"slug": "video-walkthrough", "kind": "content", "acceptance": [
        "Production brief exists", "Scene/script plan exists", "Asset checklist is included",
        "Final export requirements are documented"]},
    "Custom Automation": {"slug": "custom-automation", "kind": "workflow", "acceptance": [
        "Workflow specification exists", "Inputs and outputs are defined",
        "Dependencies are explicit", "Test and activation checklist is included"]},
}

def _safe(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-")
    return value[:80] or "project"

def _requirements(project: dict[str, Any]) -> dict[str, Any]:
    raw = project.get("requirements")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return {"items": raw}
    return {}

def _service(project: dict[str, Any]) -> dict[str, Any]:
    return SERVICE_BLUEPRINTS.get(project.get("service_name") or "", SERVICE_BLUEPRINTS["Custom Automation"])

def project_workspace(project: dict[str, Any]) -> Path:
    path = DELIVERY_ROOT / str(project["id"])
    path.mkdir(parents=True, exist_ok=True)
    return path

def generate_project(project: dict[str, Any]) -> dict[str, Any]:
    workspace = project_workspace(project)
    service = _service(project)
    req = _requirements(project)
    business = project.get("business_name") or "Client"
    website = project.get("website_url") or ""
    title = req.get("site_title") or business
    phone = req.get("phone") or ""
    email = req.get("email") or ""
    primary_cta = req.get("primary_cta") or "Contact us"
    service_list = req.get("services") or ["Services", "Contact"]
    if isinstance(service_list, str):
        service_list = [x.strip() for x in service_list.split(",") if x.strip()]
    if service["kind"] == "static_site":
        files = _generate_static_site(workspace, business, title, phone, email, primary_cta, service_list, website, req)
    else:
        files = _generate_workflow_package(workspace, project, service, req)
    manifest = {
        "project_id": str(project["id"]), "business": business,
        "service": project.get("service_name"), "generated_by": "luma-delivery-v1",
        "website": website, "requirements": req, "build_plan": build_plan(project.get("service_name"), req), "files": files,
        "acceptance_criteria": service["acceptance"],
    }
    (workspace / "delivery-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    files.append("delivery-manifest.json")
    return {"workspace": str(workspace), "files": files, "manifest": manifest}

def _generate_static_site(workspace: Path, business: str, title: str, phone: str, email: str, cta: str, services: list[str], website: str, req: dict[str, Any]) -> list[str]:
    site = workspace / "site"
    site.mkdir(parents=True, exist_ok=True)
    cards = "\n".join(f'<li><strong>{_escape(s)}</strong></li>' for s in services)
    contact = []
    if phone:
        contact.append(f'<a href="tel:{_escape(phone)}">{_escape(phone)}</a>')
    if email:
        contact.append(f'<a href="mailto:{_escape(email)}">{_escape(email)}</a>')
    contact_html = " · ".join(contact) or "Add approved contact details before launch."
    config = req.get("configuration") or {}
    capture = config.get("contact_capture") or "native_form"
    analytics = config.get("analytics") or "none"
    if capture == "netlify_forms":
        form_html = '<form name="contact" method="POST" data-netlify="true"><input type="hidden" name="form-name" value="contact"><label>Name <input name="name" required></label><label>Email <input name="email" type="email" required></label><label>Message <textarea name="message"></textarea></label><button type="submit">Send</button></form>'
    elif capture == "email_only" and email:
        form_html = f'<p><a class="btn" href="mailto:{_escape(email)}?subject=Website%20inquiry">{_escape(cta)}</a></p>'
    else:
        form_html = '<form><label>Name <input name="name" required></label><label>Email <input name="email" type="email" required></label><label>Message <textarea name="message"></textarea></label><button type="submit">Submit</button></form><p><small>Connect this form to the approved lead destination before launch.</small></p>'
    analytics_note = f'<!-- Analytics selected: {_escape(analytics)}. Add approved provider/site ID before launch. -->' if analytics != "none" else ""
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{_escape(title)} — a Luma delivery starter site.">
<title>{_escape(title)}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:0;color:#172033;background:#f8fafc}}
main{{max-width:960px;margin:auto;padding:64px 24px}}
.hero{{padding:48px 0}} h1{{font-size:clamp(2.4rem,7vw,5rem);margin:0 0 16px}}
.btn{{display:inline-block;padding:14px 20px;border-radius:10px;background:#172033;color:#fff;text-decoration:none}}
section{{background:#fff;padding:28px;border-radius:16px;margin-top:20px}}
li{{margin:10px 0}}
</style>
{analytics_note}
</head>
<body>
<main>
<section class="hero">
<p>{_escape(business)}</p>
<h1>{_escape(title)}</h1>
<p>A production-ready starter package generated from approved project requirements.</p>
<a class="btn" href="#contact">{_escape(cta)}</a>
</section>
<section><h2>Services</h2><ul>{cards}</ul></section>
<section id="contact"><h2>Contact</h2><p>{contact_html}</p>{form_html}</section>
</main>
</body>
</html>
"""
    (site / "index.html").write_text(html, encoding="utf-8")
    (workspace / "README.md").write_text(
        f"# {business} — Luma delivery\n\n"
        "This package was generated for the client project.\n\n"
        "## Launch\n\nUpload the contents of the site directory to any static web host "
        "or configure your web server document root to that directory.\n\n"
        f"Original website, if supplied: {website or 'not supplied'}\n",
        encoding="utf-8",
    )
    (workspace / "DEPLOY.md").write_text(
        "# Deployment checklist\n\n"
        "- [ ] Confirm approved production copy and assets\n"
        "- [ ] Configure the server document root to the site directory\n"
        "- [ ] Configure DNS for the approved domain\n"
        "- [ ] Enable HTTPS\n"
        "- [ ] Verify the production URL\n"
        "- [ ] Test the contact path\n"
        "- [ ] Record the final production URL in the project handoff\n",
        encoding="utf-8",
    )
    (workspace / "CLIENT-LAUNCH.md").write_text(
        "# Client launch requirements\n\n"
        "The client must supply or confirm these before Luma marks the project launch-ready:\n\n"
        "- [ ] Production domain\n"
        "- [ ] Hosting / deployment target\n"
        "- [ ] Hosting account or deployment access\n"
        "- [ ] DNS access\n"
        "- [ ] HTTPS / SSL confirmation\n"
        "- [ ] Approved production copy, branding, and assets\n"
        "- [ ] Primary contact email\n"
        "- [ ] Final production URL\n\n"
        "## Suggested resources\n\n"
        "- Cloudflare Pages — https://pages.cloudflare.com/\n"
        "- Vercel — https://vercel.com/\n"
        "- Netlify — https://www.netlify.com/\n"
        "- Cloudflare DNS — https://www.cloudflare.com/dns/\n"
        "- Netlify Forms — https://docs.netlify.com/manage/forms/setup/\n"
        "- Plausible Analytics — https://plausible.io/\n\n"
        "These are optional suggestions. Luma does not create third-party accounts or fabricate credentials.\n",
        encoding="utf-8",
    )
    return ["site/index.html", "README.md", "DEPLOY.md", "CLIENT-LAUNCH.md"]

def _generate_workflow_package(workspace: Path, project: dict[str, Any], service: dict[str, Any], req: dict[str, Any]) -> list[str]:
    spec = {
        "business": project.get("business_name"), "service": project.get("service_name"),
        "requirements": req, "inputs": req.get("inputs", []), "outputs": req.get("outputs", []),
        "dependencies": req.get("dependencies", []),
        "workflow": req.get("workflow", ["Capture input", "Validate input", "Run approved automation", "Record result", "Escalate exceptions to a human"]),
        "acceptance_criteria": service["acceptance"],
    }
    (workspace / "workflow.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    (workspace / "README.md").write_text(
        f"# {project.get('business_name', 'Client')} — {project.get('service_name', 'Automation')}\n\n"
        "This package contains the implementation specification and activation checklist. "
        "Provider credentials, domain ownership, calendars, phone numbers, or third-party accounts "
        "are never fabricated; supply them during activation.\n", encoding="utf-8")
    (workspace / "ACTIVATION.md").write_text(
        "# Activation checklist\n\n" +
        "\n".join(f"- [ ] {item}" for item in service["acceptance"]) +
        "\n- [ ] Client approval recorded\n- [ ] Production credentials supplied securely\n- [ ] Production test completed\n",
        encoding="utf-8")
    return ["workflow.json", "README.md", "ACTIVATION.md"]

def _escape(value: str) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def validate_project(project: dict[str, Any]) -> dict[str, Any]:
    workspace = project_workspace(project)
    service = _service(project)
    checks = [{"name": "manifest_exists", "passed": (workspace / "delivery-manifest.json").exists()}]
    if service["kind"] == "static_site":
        index = workspace / "site" / "index.html"
        html = index.read_text(encoding="utf-8") if index.exists() else ""
        checks.extend([
            {"name": "index_exists", "passed": index.exists()},
            {"name": "mobile_viewport", "passed": 'name="viewport"' in html},
            {"name": "primary_cta", "passed": 'href="#contact"' in html or "mailto:" in html},
            {"name": "deployment_instructions", "passed": (workspace / "DEPLOY.md").exists()},
        ])
    else:
        checks.extend([
            {"name": "workflow_spec_exists", "passed": (workspace / "workflow.json").exists()},
            {"name": "activation_checklist_exists", "passed": (workspace / "ACTIVATION.md").exists()},
        ])
    return {"passed": all(item["passed"] for item in checks), "checks": checks, "workspace": str(workspace)}

def package_project(project: dict[str, Any]) -> Path:
    workspace = project_workspace(project)
    archive = workspace.parent / f"{_safe(project.get('business_name', 'client'))}-{_safe(project.get('service_name', 'delivery'))}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in workspace.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(workspace))
    return archive

def deploy_static(project: dict[str, Any], target_root: str | None = None) -> dict[str, Any]:
    validation = validate_project(project)
    if not validation["passed"]:
        raise ValueError("Project failed delivery validation")
    if _service(project)["kind"] != "static_site":
        raise ValueError("Automatic deployment is currently supported only for static-site projects")
    target_value = target_root or os.getenv("LUMA_DEPLOY_ROOT")
    if not target_value:
        raise ValueError("LUMA_DEPLOY_ROOT is not configured")
    target = Path(target_value)
    source = project_workspace(project) / "site"
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)
    return {"deployed": True, "target": str(target), "validation": validation}


def check_live_url(url: str) -> dict:
    import httpx
    if not url:
        raise ValueError("A production URL is required")
    response = httpx.get(url, follow_redirects=True, timeout=8.0, headers={"User-Agent": "Luma/0.1 (+delivery-check)"})
    return {
        "url": str(response.url),
        "status_code": response.status_code,
        "healthy": 200 <= response.status_code < 400,
        "content_type": response.headers.get("content-type"),
    }
