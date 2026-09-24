from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tools import web_search , scrape_url 
from dotenv import load_dotenv

load_dotenv()

#model setup 
llm = ChatGoogleGenerativeAI(
    model="gemini-3.7-flash",
    max_retries=5,
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


#writer chain 

writer_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert research writer. Write clear, structured and insightful reports."),
    ("human", """Write a detailed research report on the topic below.

Topic: {topic}

Research Gathered:
{research}

Previous Critique:
{critique}

If a previous critique is provided, revise the report specifically
to address the critique. Improve source quality, remove unsupported
claims, clarify statistics, and fix any structural problems identified
by the critic.

Structure the report as:
- Introduction
- Key Findings (minimum 3 well-explained points)
- Conclusion
- Sources (list all URLs found in the research)

Be detailed, factual and professional."""),
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

