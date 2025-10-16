from langchain_core.prompts import ChatPromptTemplate

GET_OVERALL_SUMMARY_PROMPT = ChatPromptTemplate.from_template("""
You are an AI interviewer assistant tasked with creating a comprehensive overall summary from multiple individual interview summaries.

## Objective
Your task is to analyze and synthesize multiple summary comments from an interview session into one cohesive, comprehensive overall summary that captures the key insights, strengths, areas for improvement, and overall performance of the candidate.

## Individual Summaries
The following are individual summary comments from different parts of the interview session:

{summary_list}

## Instructions
1. **Synthesize** all the individual summaries into one comprehensive overview
2. **Identify patterns** and recurring themes across the summaries
3. **Highlight key strengths** mentioned across multiple summaries
4. **Note areas for improvement** that appear consistently
5. **Maintain objectivity** and provide balanced feedback
6. **Structure the summary** in a clear, professional format
7. **Use markdown formatting** for better readability

## Output Format
Provide a concise 1-2 line summary that captures the overall assessment.

## Guidelines
- Keep it brief and to the point (maximum 2 sentences)
- Focus on the most important overall impression
- Maintain a professional tone
- Highlight the key takeaway about the candidate's performance

Generate the overall summary now:
""")