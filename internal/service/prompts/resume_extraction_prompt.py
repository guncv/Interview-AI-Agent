from langchain_core.prompts import ChatPromptTemplate

RESUME_EXTRACTION_PROMPT = ChatPromptTemplate.from_template("""
Extract structured data from this resume as JSON.

Resume:
{resume_text}

CRITICAL REQUIREMENTS:
1. Return ONLY valid JSON object - NO additional text, NO markdown, NO explanations
2. Do NOT add any fields not specified below
3. Do NOT include any text before or after the JSON
4. Use EXACTLY these field names (no variations):
    - experience: Work history (company, position, dates, responsibilities)
    - project: Projects (name, description, technologies, outcomes)
    - skill_technical: Programming languages, frameworks, tools, databases, cloud platforms
    - behavior: Soft skills, leadership, teamwork, communication traits
    - is_experience: boolean (true if has work experience, could be internship or part-time job, false if don't have any work experience on company)
5. Extract ONLY information from resume (no invention)
6. If ANY category has NO information, use empty string "" as the value
    - If no work experience found: "experience": ""
    - If no projects found: "project": ""
    - If no technical skills found: "skill_technical": ""
    - If no soft skills/behavior found: "behavior": ""
7. ALL fields MUST be present in response (use "" if empty, NOT null or omit)
8. Detailed text for each field that HAS information

Your response must start with {{ and end with }} - nothing else.

Required JSON structure:
{{"experience":"...","project":"...","skill_technical":"...","behavior":"...","is_experience":true}}

Example with missing data:
{{"experience":"","project":"Built a web app...","skill_technical":"Python, React","behavior":"","is_experience":false}}
""")

