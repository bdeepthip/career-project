"""
The resume builder's three jobs, kept apart from the web pages:

1. content: start a resume from the profile, and read the editor form
2. score:   how many of a job's keywords the resume contains
3. pdf:     turn the content into a one-column PDF that applicant
            tracking systems (ATS) read cleanly

A resume's content is one plain dict, stored as JSON:

    {"name", "email", "phone", "location", "links", "headline",
     "summary", "skills", "certifications",
     "experience": [{"title", "org", "location", "dates", "bullets"}],
     "projects":   [{"name", "tech", "dates", "bullets"}],
     "education":  [{"school", "degree", "dates", "details"}]}

"bullets" is text with one bullet per line, which is how people type them.
"""

import json
import re
from collections import Counter
from pathlib import Path

from .matching import extract_skills
from .models import Education, Experience, Profile, Skill
from .timefmt import month_label

# ---------- 1. Content ----------

TEXT_FIELDS = {          # field: longest allowed length
    "name": 100, "email": 254, "phone": 40, "location": 100, "links": 300,
    "headline": 150, "summary": 1500, "skills": 1500, "certifications": 800,
}
SECTIONS = {             # section: (fields with max lengths, most entries)
    "experience": ({"title": 120, "org": 120, "location": 100, "dates": 60, "bullets": 3000}, 8),
    "projects": ({"name": 120, "tech": 200, "dates": 60, "bullets": 2000}, 6),
    "education": ({"school": 150, "degree": 200, "dates": 60, "details": 400}, 4),
}


def empty_content():
    content = {field: "" for field in TEXT_FIELDS}
    for section in SECTIONS:
        content[section] = []
    return content


def dates_label(start, end):
    """("2023-06", "2025-08") -> "Jun 2023 – Aug 2025"; no end means Present."""
    start_text = month_label(start) if start else ""
    end_text = month_label(end) if end else ("Present" if start else "")
    return " – ".join(part for part in (start_text, end_text) if part)


def from_profile(user):
    """A first draft built from everything already on the profile."""
    profile = Profile.query.filter_by(user_id=user.id).first()
    content = empty_content()
    content.update(name=user.name or "", email=user.email or "")
    if profile:
        content.update(phone=profile.phone or "", location=profile.location or "",
                       headline=profile.headline or "", summary=profile.about or "")
    if getattr(user, "phone", None) and not content["phone"]:
        content["phone"] = user.phone

    skills = Skill.query.filter_by(user_id=user.id).order_by(Skill.id).all()
    content["skills"] = ", ".join(s.skill_name for s in skills)

    jobs = (Experience.query.filter_by(user_id=user.id)
            .order_by(Experience.start_date.desc()).all())
    content["experience"] = [{
        "title": e.job_title, "org": e.company, "location": e.location or "",
        "dates": dates_label(e.start_date, e.end_date),
        "bullets": e.description or "",
    } for e in jobs][:SECTIONS["experience"][1]]

    schools = (Education.query.filter_by(user_id=user.id)
               .order_by(Education.end_year.desc()).all())
    content["education"] = [{
        "school": e.institution,
        "degree": ", ".join(part for part in (e.degree, e.field_of_study) if part),
        "dates": " – ".join(part for part in (e.start_year, e.end_year) if part),
        "details": "",
    } for e in schools][:SECTIONS["education"][1]]
    return content


def _clean(value, limit):
    return (value or "").replace("\r\n", "\n").strip()[:limit]


def from_form(form):
    """Read the editor form. Each section shows its entries plus one
    empty slot; an entry with every field blank is dropped, which is
    also how an entry is removed."""
    content = empty_content()
    for field, limit in TEXT_FIELDS.items():
        content[field] = _clean(form.get(field), limit)
    for section, (fields, most) in SECTIONS.items():
        for i in range(most):
            entry = {f: _clean(form.get(f"{section}-{i}-{f}"), limit) for f, limit in fields.items()}
            if any(entry.values()) and not form.get(f"{section}-{i}-remove"):
                content[section].append(entry)
    return content


def load(content_json):
    """Parse stored content, filling in anything missing so templates and
    the PDF never meet a missing key."""
    content = empty_content()
    try:
        stored = json.loads(content_json or "{}")
    except ValueError:
        stored = {}
    if isinstance(stored, dict):
        for field in TEXT_FIELDS:
            if isinstance(stored.get(field), str):
                content[field] = stored[field]
        for section, (fields, _) in SECTIONS.items():
            for entry in stored.get(section) or []:
                if isinstance(entry, dict):
                    content[section].append({f: str(entry.get(f) or "") for f in fields})
    return content


def dump(content):
    return json.dumps(content, ensure_ascii=False)


def bullet_lines(text):
    """Lines of a bullets field, without any bullet characters people typed."""
    lines = []
    for line in (text or "").split("\n"):
        line = re.sub(r"^\s*[-•*·–]\s*", "", line).strip()
        if line:
            lines.append(line)
    return lines


def plain_text(content):
    """All the words on the resume, for scoring."""
    parts = [content.get(f, "") for f in TEXT_FIELDS]
    for section in SECTIONS:
        for entry in content.get(section, []):
            parts += entry.values()
    return "\n".join(parts)


# ---------- 2. Keyword-match score ----------

# Words that appear in most job descriptions but say nothing about the job
STOPWORDS = set("""
a about above across after again against all also am an and any are as at be because been before being
below between both but by can could did do does doing down during each either etc every few for from
further had has have having he her here hers him his how i if in into is it its itself just least less
like may me might more most must my no nor not now of off on once only or other our ours out over own
per same shall she should so some such than that the their them then there these they this those
through to too under until up upon us very via was we were what when where which while who whom why
will with within without would you your yours
ability able across apply applicant applicants applications based benefits best candidate candidates
company compensation day days description employer employment equal etc excellent experience
experiences familiarity full help hiring including job jobs join knowledge looking new office
opportunity opportunities paid pay plus position preferred qualifications range related required
requirements responsibilities role salary skills strong team teams time understanding work working
world year years years' etc. we're you'll you're it's us. including, within. great good well using use
used build building make makes making ensure provide support supporting within across other others
one two three four five first well-being people person environment status law applicable federal
state local disability veteran gender race religion sexual orientation national origin age color
develop developing developed design designing contribute contributing organization location locations
please site needs need open process processes information application business technologies technology
positions position program programs part parts take takes taking get gets getting want wants
including include includes help helps ideas idea way ways thing things lot lots fast-paced dynamic
passionate passion exciting excited love impact impactful mission customers customer users user
currently powers hundreds millions thousands enables derive advanced insights core named
companies problems learn improvement sec per hour hours week weeks month months
""".split())

CLAUSE = re.compile(r"[,;:()\n!?]|\.(?=\s)")


def _is_word(token):
    return len(token) > 2 and token not in STOPWORDS and not token.isdigit()


NOISE_LINE = re.compile(
    r"benefit|insurance|401\(k\)|vacation|holiday|sick time|parental|maternity|salary|"
    r"\$\s?\d|equal (employment )?opportunit|accommodation|background check|"
    r"criminal|fair chance|e-verify|sponsorship|work authorization|privacy",
    re.IGNORECASE)
PLACE_LIST = re.compile(r",\s*[A-Z]{2}\b")


def _role_lines(text):
    """The parts of a job description about the work itself: drops
    benefits, pay, legal notices and lists of office locations, which
    repeat words that don't belong on a resume."""
    keep, seen = [], set()
    for line in (text or "").splitlines():
        if NOISE_LINE.search(line) or len(PLACE_LIST.findall(line)) >= 2:
            continue
        if line.strip() in seen:
            continue   # pasted descriptions often repeat the "About us" block
        seen.add(line.strip())
        keep.append(line)
    return "\n".join(keep)


def job_keywords(job_text, required_skills="", most=24):
    """The keywords a resume should contain for this job, most important
    first: named skills (from the job's skill list and from the text),
    then words and two-word phrases the description repeats."""

    keywords = []
    seen = set()

    def add(word):
        key = word.lower().strip()
        if key and key not in seen:
            seen.add(key)
            keywords.append(word.strip())

    for skill in (required_skills or "").split(","):
        add(skill)
    for skill in extract_skills(job_text or "").split(","):
        add(skill)

    # Count words and two-word phrases inside each clause, so a phrase
    # never spans a comma or a full stop
    text = _role_lines(job_text)
    words, pairs, proper, proper_words = Counter(), Counter(), Counter(), Counter()
    for clause in CLAUSE.split(text):
        raw = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]*[A-Za-z0-9+#]|[A-Za-z]", clause)
        tokens = [t.lower().strip(".-") for t in raw]
        for t, r in zip(tokens, raw):
            if _is_word(t):
                words[t] += 1
                if r[:1].isupper():
                    proper_words[t] += 1
        for (a, b), (ra, rb) in zip(zip(tokens, tokens[1:]), zip(raw, raw[1:])):
            if _is_word(a) and _is_word(b) and a != b:
                pairs[f"{a} {b}"] += 1
                if ra[:1].isupper() and rb[:1].isupper():
                    proper[f"{a} {b}"] += 1

    lowered = " ".join(re.findall(r"[a-z0-9+#.-]+", text.lower()))
    phrases = []
    for phrase, n in pairs.most_common():
        if n < 2:
            break
        if proper[phrase] == n:
            continue   # always capitalised: a name, like a customer or city
        # "natural language" + "language processing" -> "natural language processing"
        joined = next((f"{p} {phrase.split()[1]}" for p in phrases
                       if p.split()[-1] == phrase.split()[0]
                       and f"{p} {phrase.split()[1]}" in lowered), None)
        if joined:
            phrases[phrases.index(next(p for p in phrases if f"{p} {phrase.split()[1]}" == joined))] = joined
        else:
            phrases.append(phrase)
    for phrase in phrases:
        if len(keywords) >= most:
            break
        add(phrase)
    covered = " ".join(seen)
    for word, n in words.most_common():
        if n < 3 or len(keywords) >= most:
            break
        if re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", covered):
            continue   # already inside a skill or phrase above
        if proper_words[word] == n:
            continue   # always capitalised: most likely the company's own name
        add(word)
    return keywords


def _contains(text, keyword):
    """Whole-word match that ignores a simple plural either way
    ("pipeline" and "pipelines" match each other)."""
    word = keyword.lower()
    forms = {word}
    if word.endswith("s") and not word.endswith("ss") and len(word) > 4:
        forms.add(word[:-1])                      # pipelines -> pipeline
        if word.endswith("es"):
            forms.add(word[:-2])                  # processes -> process
    pattern = "|".join(re.escape(f).replace(r"\ ", r"[\s-]+")
                       for f in sorted(forms, key=len, reverse=True))
    return re.search(rf"(?<![a-z0-9])(?:{pattern})(?:e?s)?(?![a-z0-9])", text) is not None


def score(content, job_text, required_skills=""):
    """{"score": 0-100 or None, "found": [...], "missing": [...]}.
    None when there is no job text to compare against."""
    keywords = job_keywords(job_text, required_skills)
    if not keywords:
        return {"score": None, "found": [], "missing": [], "total": 0}
    text = plain_text(content).lower()
    found = [k for k in keywords if _contains(text, k)]
    missing = [k for k in keywords if k not in found]
    return {
        "score": round(len(found) * 100 / len(keywords)),
        "found": found,
        "missing": missing,
        "total": len(keywords),
    }


def job_text_for(version):
    """What a version is scored against: its Roleflow job, or pasted text."""
    if version.job is not None:
        job = version.job
        return (f"{job.title}\n{job.description or ''}\n{job.required_skills or ''}",
                job.required_skills or "")
    return version.target_text or "", ""


# ---------- 3. PDF ----------

FONT_DIR = Path(__file__).parent / "fonts"
INK = (31, 45, 42)
MUTED = (90, 102, 98)
RULE = (47, 107, 94)


def to_pdf(content):
    """A one-column, text-based PDF: real text (not an image), standard
    section names and no tables, which is what ATS parsers read best."""
    from fpdf import FPDF   # imported here so the app starts even without it

    pdf = FPDF(format="letter", unit="pt")
    pdf.set_margins(46, 40, 46)
    pdf.set_auto_page_break(True, margin=40)
    pdf.add_font("Body", "", str(FONT_DIR / "LiberationSans-Regular.ttf"))
    pdf.add_font("Body", "B", str(FONT_DIR / "LiberationSans-Bold.ttf"))
    pdf.add_font("Body", "I", str(FONT_DIR / "LiberationSans-Italic.ttf"))
    pdf.set_title(f"{content.get('name') or 'Resume'} - Resume")
    pdf.set_author(content.get("name") or "")
    pdf.set_creator("Roleflow")
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin

    def text(size, style="", color=INK):
        pdf.set_font("Body", style, size)
        pdf.set_text_color(*color)

    # Header
    text(20, "B")
    pdf.cell(width, 24, content.get("name") or "Your name", align="C", new_x="LMARGIN", new_y="NEXT")
    if content.get("headline"):
        text(10.5, "", MUTED)
        pdf.cell(width, 15, content["headline"], align="C", new_x="LMARGIN", new_y="NEXT")
    contact = [content.get(f) for f in ("location", "phone", "email") if content.get(f)]
    contact += [part.strip() for part in re.split(r"[|\n]", content.get("links") or "") if part.strip()]
    if contact:
        text(9.5, "", MUTED)
        pdf.multi_cell(width, 13, "  |  ".join(contact), align="C", new_x="LMARGIN", new_y="NEXT")

    def heading(title):
        pdf.ln(8)
        text(11, "B", RULE)
        pdf.cell(width, 15, title.upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(*RULE)
        pdf.set_line_width(0.8)
        pdf.line(pdf.l_margin, pdf.get_y() + 1, pdf.l_margin + width, pdf.get_y() + 1)
        pdf.ln(5)

    def row(left, right, style="B", size=10.5, color=INK):
        text(size, style, color)
        right_w = pdf.get_string_width(right) + 4 if right else 0
        room = width - right_w - 6
        if pdf.get_string_width(left) > room:     # never run into the dates
            while left and pdf.get_string_width(left + "…") > room:
                left = left[:-1]
            left = left.rstrip() + "…"
        pdf.cell(width - right_w, 14, left)
        pdf.cell(right_w, 14, right, align="R", new_x="LMARGIN", new_y="NEXT")

    def bullets(value):
        text(10)
        for line in bullet_lines(value):
            pdf.set_x(pdf.l_margin + 6)
            pdf.cell(10, 13.5, "•")
            pdf.multi_cell(width - 16, 13.5, line, new_x="LMARGIN", new_y="NEXT")

    def paragraph(value):
        text(10)
        pdf.multi_cell(width, 13.5, value, new_x="LMARGIN", new_y="NEXT")

    if content.get("summary"):
        heading("Summary")
        paragraph(content["summary"])

    if content.get("skills"):
        heading("Skills")
        paragraph(content["skills"])

    if content.get("experience"):
        heading("Experience")
        for entry in content["experience"]:
            row(entry.get("org") or "", entry.get("dates") or "")
            if entry.get("title") or entry.get("location"):
                row(entry.get("title") or "", entry.get("location") or "", "I", 10, MUTED)
            bullets(entry.get("bullets"))
            pdf.ln(4)

    if content.get("projects"):
        heading("Projects")
        for entry in content["projects"]:
            name = entry.get("name") or ""
            if entry.get("tech"):
                name = f"{name}  ({entry['tech']})" if name else entry["tech"]
            row(name, entry.get("dates") or "")
            bullets(entry.get("bullets"))
            pdf.ln(4)

    if content.get("education"):
        heading("Education")
        for entry in content["education"]:
            row(entry.get("school") or "", entry.get("dates") or "")
            if entry.get("degree"):
                row(entry["degree"], "", "I", 10, MUTED)
            if entry.get("details"):
                paragraph(entry["details"])
            pdf.ln(3)

    if content.get("certifications"):
        heading("Certifications")
        bullets(content["certifications"])

    return bytes(pdf.output())


def pdf_filename(content):
    name = re.sub(r"[^A-Za-z0-9]+", "_", content.get("name") or "").strip("_")
    return f"{name or 'Resume'}_Resume.pdf"
