from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tools import web_search , scrape_url 
from dotenv import load_dotenv

load_dotenv()

#model setup 
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    max_retries=2,
)

#1st agent
def build_planner_agent():

    planner_prompt = """
You are a research planning agent.

Your job is to take a research topic and break it into
5-6 specific research questions that need to be investigated.

The questions should cover:

1. Background and definition
2. Current situation and recent developments
3. Major benefits or positive impacts
4. Major challenges, risks, or limitations
5. Evidence, statistics, or real-world examples
6. Future outlook

Rules:
- Questions must be specific and researchable.
- Avoid duplicate questions.
- Avoid questions that are too broad.
- Questions should be answerable using reliable web sources.

Return ONLY a numbered list of research questions.
"""

    return create_agent(
        model=llm,
        tools=[],
        system_prompt=planner_prompt
    )


#2nd agent 
def build_search_agent():
    return create_agent(
        model = llm,
        tools= [web_search]
    )

#3rd agent 

def build_reader_agent():
    return create_agent(
        model = llm,
        tools = [scrape_url]
    )

# 5. NEW: Fact checker agent
def build_fact_checker_agent():
    return create_agent(
        model=llm,
        tools=[],
        system_prompt="""
        You are a research fact-checking agent.

        Review the research evidence and identify:
        - Claims supported by evidence
        - Claims that are only partially supported
        - Contradictions between sources
        - Claims that cannot be verified

        Never invent facts, evidence, or citations.
        Clearly explain which claims need further verification.
        """
    )


# 6. NEW: Research gap analysis agent
def build_gap_analysis_agent():
    return create_agent(
        model=llm,
        tools=[web_search],
        system_prompt="""
        You are a research gap analysis agent.

        Review the research questions and collected evidence.
        Identify:
        - Important unanswered research questions
        - Missing data or statistics
        - Weak or outdated evidence
        - Conflicting findings that need investigation
        - Areas requiring additional research

        Use web_search when additional evidence is needed.
        Avoid repeating searches that have already been completed.
        Do not invent findings or citations.
        """
    )


#writer chain 

writer_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
You are a professional research analyst and report writer.
Produce a complete, well-organized, evidence-based report.
Use Markdown headings and subheadings.
Never invent statistics, quotations, sources, or URLs.
Clearly distinguish established findings from uncertainty.
If evidence is insufficient for a section, state that limitation.

CITATION RULES:
- Cite PDF evidence inline using [filename, p. X].
- Include the actual filename and page number for claims
  supported by uploaded PDFs.
- List web URLs only when they are provided in the research evidence.
- Never invent a URL, PDF title, page number, statistic, or citation.
- If web and PDF sources disagree, explain the disagreement.
- Do not cite a source unless the supplied evidence supports the claim.
"""
    ),
    (
        "human",
        """
Write a comprehensive research report on this topic:

TOPIC:
{topic}

RESEARCH EVIDENCE:
{research}

PREVIOUS CRITIQUE AND FACT-CHECK FINDINGS:
{critique}

Use the following structure:

# Research Report: [Topic]

## Executive Summary
Summarize the topic, principal findings, and overall conclusion.

## 1. Introduction
Explain the background, context, scope, and importance of the topic.

## 2. Research Objectives and Questions
List the main objectives and research questions.

## 3. Research Methodology
Explain how the available web evidence was gathered and analyzed.
Do not claim that formal systematic methods were used unless they were.

## 4. Key Findings
Present at least three substantive findings, with evidence and
source attribution where available.

## 5. Detailed Analysis
Discuss the major themes, benefits, challenges, examples, and
implications relevant to the topic.

## 6. Research Gaps and Limitations
Identify unanswered questions, missing evidence, and limitations
of the sources. Do not invent a separate gap analysis if none
was supplied.

## 7. Recommendations and Future Outlook
Provide practical recommendations and reasonable future directions,
distinguishing evidence from forecasts.

## 8. Conclusion
Synthesize the most important findings and answer the main
research question.

## References
List the sources used in the report.

For web sources, include the source title and URL when available.
For uploaded PDFs, include the actual filename and relevant page number.
Only include sources present in the supplied research evidence.
Never fabricate a citation.

Write detailed, meaningful content under each relevant heading.
Do not output a table of contents without the actual report.
Do not mention that you are an AI.
"""
    ),
])

writer_chain = writer_prompt | llm | StrOutputParser()

#critic_chain 

critic_prompt = ChatPromptTemplate.from_messages([
     ("system", "You are a sharp and constructive research critic. Be honest and specific."),
    ("human", """Review the research report below and evaluate it strictly.

Report:
{report}

Respond in this exact format:

Score: X/10

Strengths:
- ...
- ...

Areas to Improve:
- ...
- ...

One line verdict:
..."""),
])

critic_chain = critic_prompt | llm | StrOutputParser()

