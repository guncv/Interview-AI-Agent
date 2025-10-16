from langchain_core.prompts import ChatPromptTemplate

BIAS_PROMPT = ChatPromptTemplate.from_template("""
Extract key terms from this resume for speech-to-text accuracy. Return comma-separated list only.

Resume:
{resume_text}

Extract:
- Full name, nicknames
- Universities, degrees, majors (full & abbreviated)
- Company names, job titles
- Project names
- Programming languages, frameworks, databases, cloud platforms, tools
- Certifications, awards
- Technical acronyms & jargon

Rules:
- Extract ONLY terms from resume (no invention)
- Include proper capitalization (JavaScript, PostgreSQL, AWS)
- Both full names & abbreviations
- Prioritize proper nouns & technical terms

Output format (comma-separated):
John Smith, Stanford University, Computer Science, Google, AWS, React, TypeScript, PostgreSQL, Docker
""")
