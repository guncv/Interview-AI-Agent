from langchain_core.prompts import ChatPromptTemplate

BIAS_PROMPT = ChatPromptTemplate.from_template("""
You are an expert at extracting key terms from resumes that need accurate speech-to-text transcription.

Your task is to extract ALL important terms from the following resume text that should be recognized correctly during a speech interview. Focus on:

1. **Personal Information:**
    - Full name (first name, middle name, last name)
    - Nicknames or preferred names

2. **Educational Background:**
    - University names (full and abbreviated forms)
    - College names
    - Degree names and abbreviations (e.g., "Bachelor of Science", "B.S.", "Master's", "PhD")
    - Major/Minor fields of study
    - Academic programs or specializations

3. **Professional Experience:**
    - Company names (full legal names and common short forms)
    - Organization names
    - Department names
    - Job titles and roles

4. **Projects:**
    - Project names and titles
    - Application names
    - System names

5. **Technical Skills:**
    - Programming languages (Python, JavaScript, TypeScript, Java, C++, Go, Rust, etc.)
    - Frameworks and libraries (React, Angular, Vue, Django, Flask, FastAPI, TensorFlow, PyTorch, etc.)
    - Databases (PostgreSQL, MySQL, MongoDB, Redis, Cassandra, etc.)
    - Cloud platforms (AWS, Azure, GCP, DigitalOcean, etc.)
    - Tools and software (Docker, Kubernetes, Jenkins, Git, Jira, etc.)
    - Methodologies (Agile, Scrum, DevOps, CI/CD, etc.)
    - Protocols and standards (REST, GraphQL, gRPC, OAuth, JWT, etc.)

6. **Certifications and Awards:**
    - Certification names
    - Award titles
    - Competition names

7. **Domain-Specific Terms:**
    - Technical jargon specific to the candidate's field
    - Industry-specific terminology
    - Acronyms and abbreviations

**Instructions:**
- Extract ONLY the terms that appear in the resume text below
- Include both full names and common abbreviations/acronyms
- For technologies, include proper capitalization (e.g., "JavaScript", "PostgreSQL", "AWS")
- Include company names exactly as they appear
- DO NOT make up or invent terms that are not in the resume
- Return the terms as a comma-separated list
- Prioritize proper nouns and technical terms that are often mispronounced or misrecognized by speech-to-text

**Resume Text:**
{resume_text}

**Output Format:**
Provide only the comma-separated list of terms, no additional explanation or formatting. Example:
John Smith, Stanford University, Computer Science, Google, Amazon Web Services, AWS, React, TypeScript, PostgreSQL, Docker, Kubernetes, Python, TensorFlow, PyTorch

**Extracted Terms:**
""")
