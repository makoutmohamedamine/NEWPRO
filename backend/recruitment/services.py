from __future__ import annotations

import json
import re
import zlib
import zipfile
from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

from django.core.files.uploadedfile import UploadedFile
from django.db.models import Avg, Count, Max

from .models import Candidate, JobProfile


EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,5}\d{2,4}")
YEAR_RE = re.compile(r"\b(20\d{2}|19\d{2})\b")

SKILL_CATALOG = [
    "python",
    "django",
    "flask",
    "fastapi",
    "react",
    "javascript",
    "typescript",
    "sql",
    "postgresql",
    "mysql",
    "power bi",
    "excel",
    "machine learning",
    "deep learning",
    "nlp",
    "data analysis",
    "pandas",
    "numpy",
    "scikit-learn",
    "tensorflow",
    "keras",
    "azure",
    "aws",
    "docker",
    "git",
    "html",
    "css",
    "node.js",
    "java",
    "spring",
    "marketing digital",
    "seo",
    "communication",
    "figma",
    "ui/ux",
]

PROFILE_RULES = {
    "Developpeur Full Stack": ["react", "javascript", "django", "python", "sql", "api"],
    "Data Analyst": ["power bi", "excel", "sql", "python", "pandas", "data analysis"],
    "Ingenieur IA/NLP": ["machine learning", "nlp", "scikit-learn", "tensorflow", "bert", "python"],
    "Marketing Digital": ["marketing digital", "seo", "communication", "social media", "analytics"],
}

EDUCATION_RULES = [
    ("Doctorat", ["doctorat", "phd"]),
    ("Master", ["master", "bac+5", "ingenieur", "engineering"]),
    ("Licence", ["licence", "bachelor", "bac+3"]),
    ("DUT/BTS", ["dut", "bts", "bac+2"]),
]


@dataclass
class ParsedCv:
    raw_text: str
    full_name: str
    email: str
    phone: str
    current_title: str
    education_level: str
    skills: list[str]
    years_experience: Decimal
    summary: str


def extract_text_from_upload(uploaded_file: UploadedFile) -> str:
    suffix = Path(uploaded_file.name).suffix.lower()
    data = uploaded_file.read()
    uploaded_file.seek(0)

    if suffix == ".pdf":
        return _extract_pdf_text(data)
    if suffix == ".docx":
        return _extract_docx_text(data)
    return data.decode("utf-8", errors="ignore")


def _extract_docx_text(data: bytes) -> str:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        xml_content = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml_content)
    paragraphs = [node.text.strip() for node in root.iter() if node.text and node.text.strip()]
    return "\n".join(paragraphs)


def _decode_pdf_string(value: bytes) -> str:
    output: list[str] = []
    index = 0
    while index < len(value):
        current = value[index]
        if current == 92 and index + 1 < len(value):
            index += 1
            escaped = value[index]
            replacements = {
                110: "\n",
                114: "\r",
                116: "\t",
                98: "\b",
                102: "\f",
                40: "(",
                41: ")",
                92: "\\",
            }
            if escaped in replacements:
                output.append(replacements[escaped])
            elif 48 <= escaped <= 55:
                octal = bytes([escaped])
                for _ in range(2):
                    if index + 1 < len(value) and 48 <= value[index + 1] <= 55:
                        index += 1
                        octal += bytes([value[index]])
                    else:
                        break
                output.append(chr(int(octal, 8)))
            else:
                output.append(chr(escaped))
        else:
            output.append(chr(current))
        index += 1
    return "".join(output)


def _extract_pdf_text(data: bytes) -> str:
    streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S)
    fragments: list[str] = []
    for stream in streams:
        try:
            payload = zlib.decompress(stream)
        except Exception:
            payload = stream
        if b"BT" not in payload:
            continue
        for match in re.finditer(rb"\[(.*?)\]TJ|\((.*?)\)Tj", payload, re.S):
            segment = match.group(1) if match.group(1) is not None else match.group(2)
            if match.group(1) is not None:
                parts = re.findall(rb"\((.*?)\)", segment, re.S)
                text = "".join(_decode_pdf_string(part) for part in parts)
            else:
                text = _decode_pdf_string(segment)
            if text.strip():
                fragments.append(text)
    return "\n".join(fragments)


def parse_cv_text(raw_text: str, fallback_name: str = "Candidat inconnu") -> ParsedCv:
    normalized = " ".join(raw_text.split())
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    first_line = lines[0] if lines else fallback_name

    email_match = EMAIL_RE.search(raw_text)
    phone_match = PHONE_RE.search(raw_text)
    email = email_match.group(0) if email_match else ""
    phone = phone_match.group(0) if phone_match else ""
    skills = [skill for skill in SKILL_CATALOG if skill in normalized.lower()]
    education = _detect_education(normalized.lower())
    years_experience = _estimate_experience(raw_text)
    current_title = _detect_title(normalized.lower(), skills)
    full_name = _guess_name(first_line, email, fallback_name)
    summary = " ".join(lines[:3])[:280]

    return ParsedCv(
        raw_text=raw_text.strip(),
        full_name=full_name,
        email=email,
        phone=phone,
        current_title=current_title,
        education_level=education,
        skills=skills,
        years_experience=years_experience,
        summary=summary,
    )


def _guess_name(first_line: str, email: str, fallback_name: str) -> str:
    clean_line = re.sub(r"[^A-Za-zÀ-ÿ' -]", " ", first_line).strip()
    words = [word for word in clean_line.split() if len(word) > 1]
    if 1 < len(words) <= 5:
        return " ".join(word.capitalize() for word in words)
    if email:
        local_part = email.split("@", 1)[0].replace(".", " ").replace("_", " ")
        return " ".join(part.capitalize() for part in local_part.split())
    return fallback_name


def _detect_education(text: str) -> str:
    for label, patterns in EDUCATION_RULES:
        if any(pattern in text for pattern in patterns):
            return label
    return "Non precise"


def _estimate_experience(text: str) -> Decimal:
    years = sorted({int(year) for year in YEAR_RE.findall(text)})
    if len(years) >= 2:
        return Decimal(str(max(0, min(25, max(years) - min(years)))))
    lowered = text.lower()
    explicit = re.search(r"(\d{1,2})\s*\+?\s*an", lowered)
    if explicit:
        return Decimal(explicit.group(1))
    return Decimal("0")


def _detect_title(text: str, skills: list[str]) -> str:
    if {"react", "django", "python"} & set(skills):
        return "Developpeur Full Stack"
    if {"power bi", "data analysis", "pandas"} & set(skills):
        return "Data Analyst"
    if {"machine learning", "nlp", "tensorflow"} & set(skills):
        return "Ingenieur IA/NLP"
    if {"marketing digital", "seo"} & set(skills):
        return "Marketing Digital"
    for title in PROFILE_RULES:
        if title.lower() in text:
            return title
    return "Profil generaliste"


def classify_candidate(parsed_cv: ParsedCv, job_profiles: list[JobProfile]) -> JobProfile | None:
    if not job_profiles:
        return None

    best_job = None
    best_score = -1
    for job in job_profiles:
        overlap = len(set(parsed_cv.skills) & set(job.keyword_list))
        title_bonus = 2 if job.name.lower() in parsed_cv.current_title.lower() else 0
        score = overlap + title_bonus
        if score > best_score:
            best_score = score
            best_job = job

    if best_score <= 0:
        return None
    return best_job


def compute_match_score(parsed_cv: ParsedCv, job_profile: JobProfile | None) -> Decimal:
    if not job_profile:
        return Decimal("45.00")

    keywords = set(job_profile.keyword_list)
    if not keywords:
        return Decimal("50.00")

    overlap = len(set(parsed_cv.skills) & keywords)
    keyword_ratio = Decimal(overlap) / Decimal(len(keywords))
    experience_bonus = Decimal("0.15") if parsed_cv.years_experience >= job_profile.minimum_experience_years else Decimal("0.05")
    education_bonus = Decimal("0.10") if parsed_cv.education_level in {"Master", "Doctorat"} else Decimal("0.03")
    title_bonus = Decimal("0.10") if job_profile.name.lower() in parsed_cv.current_title.lower() else Decimal("0")

    total = min(Decimal("1"), keyword_ratio * Decimal("0.65") + experience_bonus + education_bonus + title_bonus)
    return (total * Decimal("100")).quantize(Decimal("0.01"))


def create_candidate_from_upload(
    uploaded_file: UploadedFile,
    *,
    source: str,
    source_email: str = "",
    target_job: JobProfile | None = None,
) -> Candidate:
    raw_text = extract_text_from_upload(uploaded_file)
    parsed_cv = parse_cv_text(raw_text, fallback_name=Path(uploaded_file.name).stem.replace("_", " "))
    available_jobs = list(JobProfile.objects.all())
    detected_job = target_job or classify_candidate(parsed_cv, available_jobs)
    score = compute_match_score(parsed_cv, detected_job)

    candidate = Candidate.objects.create(
        full_name=parsed_cv.full_name,
        email=parsed_cv.email,
        phone=parsed_cv.phone,
        source=source,
        source_email=source_email,
        current_title=parsed_cv.current_title,
        profile_label=(detected_job.name if detected_job else parsed_cv.current_title),
        education_level=parsed_cv.education_level,
        extracted_skills=", ".join(parsed_cv.skills),
        years_experience=parsed_cv.years_experience,
        match_score=score,
        summary=parsed_cv.summary,
        raw_text=parsed_cv.raw_text,
        cv_file=uploaded_file,
        cv_filename=uploaded_file.name,
        target_job=detected_job,
        status=Candidate.Status.NEW,
    )
    return candidate


def candidate_to_dict(candidate: Candidate) -> dict:
    return {
        "id": candidate.id,
        "fullName": candidate.full_name,
        "email": candidate.email,
        "phone": candidate.phone,
        "source": candidate.source,
        "sourceEmail": candidate.source_email,
        "status": candidate.status,
        "currentTitle": candidate.current_title,
        "profileLabel": candidate.profile_label,
        "educationLevel": candidate.education_level,
        "skills": candidate.skills_list,
        "yearsExperience": float(candidate.years_experience),
        "matchScore": float(candidate.match_score),
        "summary": candidate.summary,
        "notes": candidate.notes,
        "targetJob": candidate.target_job.name if candidate.target_job else None,
        "cvFileName": candidate.cv_filename,
        "cvUrl": candidate.cv_file.url if candidate.cv_file else "",
        "createdAt": candidate.created_at.isoformat(),
    }


def job_profile_to_dict(job_profile: JobProfile) -> dict:
    return {
        "id": job_profile.id,
        "name": job_profile.name,
        "description": job_profile.description,
        "keywords": job_profile.keyword_list,
        "minimumExperienceYears": job_profile.minimum_experience_years,
    }


def dashboard_payload(candidates) -> dict:
    aggregate = candidates.aggregate(
        total=Count("id"),
        average_score=Avg("match_score"),
        best_score=Max("match_score"),
    )
    by_status = {item["status"]: item["count"] for item in candidates.values("status").annotate(count=Count("id"))}
    by_profile = {
        item["profile_label"] or "Non classe": item["count"]
        for item in candidates.values("profile_label").annotate(count=Count("id"))
    }
    top_candidates = [candidate_to_dict(candidate) for candidate in candidates.order_by("-match_score", "-created_at")[:5]]

    return {
        "stats": {
            "totalCandidates": aggregate["total"] or 0,
            "averageScore": float(aggregate["average_score"] or 0),
            "bestScore": float(aggregate["best_score"] or 0),
            "newCandidates": by_status.get(Candidate.Status.NEW, 0),
        },
        "statusDistribution": by_status,
        "profileDistribution": by_profile,
        "topCandidates": top_candidates,
    }


def seed_demo_content() -> None:
    jobs = [
        {
            "name": "Developpeur Full Stack",
            "description": "Developpement web frontend/backend, API REST, bases de donnees.",
            "keywords": "python, django, react, javascript, sql, api, html, css",
            "minimum_experience_years": 2,
        },
        {
            "name": "Data Analyst",
            "description": "Analyse de donnees, reporting, tableaux de bord, SQL et Power BI.",
            "keywords": "sql, python, pandas, excel, power bi, data analysis, reporting",
            "minimum_experience_years": 1,
        },
        {
            "name": "Ingenieur IA/NLP",
            "description": "NLP, machine learning, extraction d'information et classification.",
            "keywords": "python, nlp, machine learning, scikit-learn, tensorflow, bert",
            "minimum_experience_years": 2,
        },
        {
            "name": "Marketing Digital",
            "description": "SEO, acquisition, communication digitale et analytics.",
            "keywords": "marketing digital, seo, communication, analytics, social media",
            "minimum_experience_years": 1,
        },
    ]

    for payload in jobs:
        JobProfile.objects.get_or_create(name=payload["name"], defaults=payload)

    if Candidate.objects.exists():
        return

    samples = [
        {
            "full_name": "Salma Bennani",
            "email": "salma.bennani@example.com",
            "phone": "+212 612345678",
            "source": Candidate.Source.EMAIL,
            "source_email": "careers@example.com",
            "current_title": "Data Analyst",
            "profile_label": "Data Analyst",
            "education_level": "Master",
            "extracted_skills": "python, sql, pandas, power bi, excel",
            "years_experience": Decimal("3.0"),
            "match_score": Decimal("91.50"),
            "summary": "Analyste data avec experience en reporting, SQL, Power BI et automatisation Python.",
            "raw_text": "Python SQL Power BI pandas analyse de donnees master 2021 2024",
            "cv_filename": "salma_bennani_cv.pdf",
            "status": Candidate.Status.SHORTLISTED,
            "target_job_name": "Data Analyst",
        },
        {
            "full_name": "Youssef Alaoui",
            "email": "youssef.alaoui@example.com",
            "phone": "+212 623456789",
            "source": Candidate.Source.MANUAL,
            "source_email": "",
            "current_title": "Developpeur Full Stack",
            "profile_label": "Developpeur Full Stack",
            "education_level": "Master",
            "extracted_skills": "python, django, react, javascript, sql, docker",
            "years_experience": Decimal("4.0"),
            "match_score": Decimal("95.20"),
            "summary": "Developpeur full stack specialise en React, Django et architecture API REST.",
            "raw_text": "React Django Python SQL Docker API Master 2020 2024",
            "cv_filename": "youssef_alaoui_cv.docx",
            "status": Candidate.Status.IN_REVIEW,
            "target_job_name": "Developpeur Full Stack",
        },
        {
            "full_name": "Imane El Idrissi",
            "email": "imane.elidrissi@example.com",
            "phone": "+212 634567890",
            "source": Candidate.Source.EMAIL,
            "source_email": "jobs@example.com",
            "current_title": "Ingenieur IA/NLP",
            "profile_label": "Ingenieur IA/NLP",
            "education_level": "Doctorat",
            "extracted_skills": "python, nlp, machine learning, scikit-learn, tensorflow",
            "years_experience": Decimal("2.0"),
            "match_score": Decimal("93.10"),
            "summary": "Profil IA oriente NLP, extraction de texte et classification automatique.",
            "raw_text": "Python NLP Tensorflow scikit-learn doctorat 2022 2024",
            "cv_filename": "imane_elidrissi_cv.pdf",
            "status": Candidate.Status.NEW,
            "target_job_name": "Ingenieur IA/NLP",
        },
    ]

    job_map = {job.name: job for job in JobProfile.objects.all()}
    for sample in samples:
        target_job = job_map[sample.pop("target_job_name")]
        Candidate.objects.create(target_job=target_job, **sample)


def export_candidates_snapshot() -> str:
    payload = [candidate_to_dict(candidate) for candidate in Candidate.objects.select_related("target_job")]
    return json.dumps(payload, ensure_ascii=False)
