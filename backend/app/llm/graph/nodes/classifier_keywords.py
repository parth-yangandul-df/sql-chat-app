"""classifier_keywords.py — shared keyword routing for intent classification.

Contains all keyword frozensets and the _keyword_route() function used by both
the default embedding path and the Groq extractor path.
"""

# Common English stop words that carry no domain signal
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "do",
        "does",
        "did",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "by",
        "from",
        "and",
        "or",
        "but",
        "not",
        "no",
        "so",
        "if",
        "all",
        "show",
        "me",
        "my",
        "their",
        "list",
        "get",
        "who",
        "what",
        "where",
        "when",
        "how",
        "which",
        "one",
        "these",
        "those",
        "them",
        "this",
        "that",
        "it",
        "its",
        "i",
        "we",
        "you",
        "they",
        "he",
        "she",
    }
)

# ---------------------------------------------------------------------------
# First-person pronouns — checked on raw tokens (NOT stripped via _STOP_WORDS)
# Used to gate user_self intent: only valid when user is asking about themselves.
# ---------------------------------------------------------------------------
_FIRST_PERSON_WORDS: frozenset[str] = frozenset(
    {
        "my",
        "i",
        "me",
        "mine",
        "myself",
        "i'm",
        "i've",
        "i'll",
        "i'd",
    }
)


def _has_first_person(question: str) -> bool:
    """Return True if the question contains any first-person pronoun."""
    tokens = {w.lower().strip("?.,!;:'\"") for w in question.split()}
    return bool(tokens & _FIRST_PERSON_WORDS)


def _has_person_name(question: str) -> bool:
    """Return True if question contains a person name pattern.

    Detects sequences of 2+ consecutive capitalized words that look like
    a person's name (e.g., "Gautham R M", "John Smith", "Jane Doe").
    Used to guard _USER_SELF_KEYWORDS — queries about named people should
    not route to user_self even if they contain "my" or "me".
    """
    words = question.split()
    capitalized_count = 0

    for word in words:
        clean_word = word.strip("?.,!;:'\"")
        if clean_word and clean_word[0].isupper() and clean_word[0].isalpha():
            capitalized_count += 1
            if capitalized_count >= 2:
                return True
        else:
            capitalized_count = 0

    return False


# ---------------------------------------------------------------------------
# Keyword pre-check sets — fast-path routing before embedding similarity.
# Each set covers unambiguous signals that embedding cosine similarity
# frequently misroutes due to short/generic catalog descriptions.
# ---------------------------------------------------------------------------

_SKILL_KEYWORDS: frozenset[str] = frozenset(
    {
        # Languages
        "python",
        "java",
        "javascript",
        "typescript",
        "golang",
        "go",
        "rust",
        "kotlin",
        "swift",
        "scala",
        "ruby",
        "php",
        "perl",
        "matlab",
        "c#",
        "c++",
        "vb.net",
        ".net",
        # Frameworks / platforms
        "react",
        "angular",
        "vue",
        "svelte",
        "nextjs",
        "next.js",
        "django",
        "flask",
        "fastapi",
        "spring",
        "springboot",
        "nodejs",
        "node.js",
        "express",
        "nestjs",
        "dotnet",
        "asp.net",
        "blazor",
        # Data / cloud / infra
        "nosql",
        "mongodb",
        "postgres",
        "postgresql",
        "mysql",
        "redis",
        "elasticsearch",
        "kafka",
        "aws",
        "azure",
        "gcp",
        "kubernetes",
        "k8s",
        "terraform",
        "ansible",
        # Mobile / AI
        "android",
        "ios",
        "flutter",
        "tensorflow",
        "pytorch",
        # Database query language
        "sql",
    }
)

# "bench" / "benched" are unambiguous — "available" / "free" excluded (too broad)
_BENCH_KEYWORDS: frozenset[str] = frozenset(
    {
        "bench",
        "benched",
    }
)

# "skills of X" / "skills for X" — specific person skill queries
# Must be checked BEFORE generic bench/skill to catch "skills of Abhijeet Desai" patterns
_SKILLS_OF_KEYWORDS: frozenset[str] = frozenset(
    {
        "skills of",
        "skills for",
        "skill set of",
        "skill set for",
        "tech skills of",
        "tech skills for",
        "what skills does",
        "what skills do",
        "what are the skills of",
        "what are the skill",
    }
)

_OVERDUE_KEYWORDS: frozenset[str] = frozenset(
    {
        "overdue",
        "delayed",
        "behind schedule",
        "past deadline",
        "past due",
        "past end date",
    }
)

_TIMELINE_KEYWORDS: frozenset[str] = frozenset(
    {
        "timeline",
        "duration",
        "start date",
        "end date",
        "how long",
        "when does",
        "when did",
        "deadline",
    }
)

_BUDGET_KEYWORDS: frozenset[str] = frozenset(
    {
        "budget",
        "burn rate",
    }
)

_UNAPPROVED_KEYWORDS: frozenset[str] = frozenset(
    {
        "unapproved",
        "pending approval",
        "not approved",
        "waiting for approval",
        "unreviewed",
        "pending timesheet",
    }
)

# "show all active client*" pattern — must be checked BEFORE generic "active" matching
# to route to active_clients instead of client_projects or other intents
_ACTIVE_CLIENT_KEYWORDS: frozenset[str] = frozenset(
    {
        "active client",
        "active clients",
        "all active client",
        "all active clients",
        "list active client",
        "list active clients",
        "show active client",
        "show active clients",
        "current client",
        "current clients",
        "all current client",
        "all current clients",
    }
)

# "show all active project*" pattern — must be checked BEFORE generic "active" matching
_ACTIVE_PROJECT_KEYWORDS: frozenset[str] = frozenset(
    {
        "active project",
        "active projects",
        "all active project",
        "all active projects",
        "list active project",
        "list active projects",
        "show active project",
        "show active projects",
        "current project",
        "current projects",
        "all current project",
        "all current projects",
        "ongoing project",
        "ongoing projects",
        "all ongoing project",
        "all ongoing projects",
    }
)

# "show all active resource*" / "active employees" — checked BEFORE skill/bench matching
_ACTIVE_RESOURCE_KEYWORDS: frozenset[str] = frozenset(
    {
        "active resource",
        "active resources",
        "all active resource",
        "all active resources",
        "list active resource",
        "list active resources",
        "show active resource",
        "show active resources",
        "active employee",
        "active employees",
        "all active employee",
        "all active employees",
        "show active employee",
        "show active employees",
        "list active employee",
        "list active employees",
        "active staff",
        "all active staff",
        "show active staff",
    }
)

_PROJECT_RESOURCES_KEYWORDS: frozenset[str] = frozenset(
    {
        "working on project",
        "works on project",
        "assigned to project",
        "who is on project",
        "who are on project",
        "on the project",
        "team on project",
        "team for project",
        "members of project",
        "resources on project",
        "resources for project",
        "resources assigned",
        "working on the project",
        "assigned to the project",
        "who is working on",
        "who works on",
        "team members on",
    }
)

# "projects for client X" — explicit filter-by-client patterns
# Must NOT include "client projects" (ambiguous with client_projects intent)
_PROJECT_BY_CLIENT_KEYWORDS: frozenset[str] = frozenset(
    {
        "projects for client",
        "show projects for client",
        "client's projects",
        "projects of client",
    }
)

# "resource project assignments" — who is assigned to which projects for a specific person
_RESOURCE_PROJECT_KEYWORDS: frozenset[str] = frozenset(
    {
        "project assignment",
        "project assignments",
        "who is assigned to",
        "who are assigned to",
        "resources assigned to",
        "resource assigned to",
        "assigned projects",
        "person's projects",
        "employee projects",
        "staff projects",
        "team member projects",
    }
)

# Specific "my X" patterns must be checked BEFORE generic "my project(s)" in _keyword_route
# to prevent substring matches (e.g., "my project" matching "my utilization").
_USER_UTILIZATION_KEYWORDS: frozenset[str] = frozenset(
    {
        "my utilization",
        "my utilization for",
        "my hours",
        "my hours for",
    }
)

_USER_ALLOCATION_KEYWORDS: frozenset[str] = frozenset(
    {
        "my allocation",
        "my allocation for",
        "show my allocation",
    }
)

_USER_SELF_KEYWORDS: frozenset[str] = frozenset(
    {
        "my timesheet",
        "my timesheets",
        "show my timesheet",
        "show my timesheets",
        "my project",
        "my projects",
        "show my project",
        "show my projects",
    }
)

_MY_SKILLS_KEYWORDS: frozenset[str] = frozenset(
    {
        "my skill",
        "my skills",
        "show my skill",
        "show my skills",
    }
)

_REPORTS_TO_KEYWORDS: frozenset[str] = frozenset(
    {
        "reports to",
        "reporting to",
        "who reports to",
        "direct reports",
        "reportees of",
        "team under",
        "subordinates of",
        "who report to",
    }
)


def _keyword_route(question: str) -> tuple[str, str] | None:
    """Check keyword sets and return (intent_name, domain) if a pre-check fires.

    Order matters — bench checked before skill to avoid "bench developers"
    routing to resource_by_skill instead of benched_resources.
    Returns None if no keyword guard matches.
    """
    q = question.lower()
    # Check most specific patterns FIRST — reports_to before resource_project
    if any(kw in q for kw in _REPORTS_TO_KEYWORDS):
        return ("reports_to", "resource")
    # Check most specific patterns FIRST — resource_project before project_resources
    if any(kw in q for kw in _RESOURCE_PROJECT_KEYWORDS):
        return ("resource_project_assignments", "resource")
    # Check most specific patterns FIRST — project_resources before active_projects
    if any(kw in q for kw in _PROJECT_RESOURCES_KEYWORDS):
        return ("project_resources", "project")
    # "projects for client X" — explicit filter-by-client patterns
    if any(kw in q for kw in _PROJECT_BY_CLIENT_KEYWORDS):
        return ("project_by_client", "project")
    # USER_UTILIZATION must be checked BEFORE generic _USER_SELF_KEYWORDS
    # to prevent "my project" from substring-matching "my utilization"
    if any(kw in q for kw in _USER_UTILIZATION_KEYWORDS):
        return ("my_utilization", "user_self")
    # USER_ALLOCATION must be checked AFTER my_utilization and BEFORE generic keywords
    if any(kw in q for kw in _USER_ALLOCATION_KEYWORDS):
        return ("my_allocation", "user_self")
    # MY_SKILLS must be checked BEFORE _USER_SELF_KEYWORDS to route "my skills" to my_skills
    if any(kw in q for kw in _MY_SKILLS_KEYWORDS):
        return ("my_skills", "user_self")
    # USER_SELF — "my projects", "my timesheets" etc. route to user_self
    # Skip if question contains a person name (e.g., "Show me Gautham R M project assignments")
    # — in that case "me" refers to someone else, not the current user.
    if not _has_person_name(question) and any(kw in q for kw in _USER_SELF_KEYWORDS):
        return ("my_projects", "user_self")
    if any(kw in q for kw in _ACTIVE_CLIENT_KEYWORDS):
        return ("active_clients", "client")
    if any(kw in q for kw in _ACTIVE_PROJECT_KEYWORDS):
        return ("active_projects", "project")
    if any(kw in q for kw in _ACTIVE_RESOURCE_KEYWORDS):
        return ("active_resources", "resource")
    if any(kw in q for kw in _BENCH_KEYWORDS):
        # If a skill keyword also appears, route to benched_by_skill
        if any(kw in q for kw in _SKILL_KEYWORDS):
            return ("benched_by_skill", "resource")
        return ("benched_resources", "resource")
    if any(kw in q for kw in _SKILL_KEYWORDS):
        return ("resource_by_skill", "resource")
    # "skills of X" — checked AFTER skill check so "skills of X who know Python" routes correctly
    if any(kw in q for kw in _SKILLS_OF_KEYWORDS):
        return ("resource_skills_list", "resource")
    if any(kw in q for kw in _OVERDUE_KEYWORDS):
        return ("overdue_projects", "project")
    if any(kw in q for kw in _TIMELINE_KEYWORDS):
        return ("project_timeline", "project")
    if any(kw in q for kw in _BUDGET_KEYWORDS):
        return ("project_budget", "project")
    if any(kw in q for kw in _UNAPPROVED_KEYWORDS):
        return ("unapproved_timesheets", "timesheet")
    return None
